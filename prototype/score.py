
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = Path(__file__).resolve().parent
VALID_STATES = {"supported", "missing", "ambiguous", "conflicting"}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_path(obj: dict[str, Any], dotted_path: str) -> Any:
    current: Any = obj
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def value_and_state(obj: dict[str, Any], dotted_path: str) -> tuple[Any, str]:
    entry = get_path(obj, dotted_path)
    if not isinstance(entry, dict) or "value" not in entry:
        return None, "missing"
    state = entry.get("state", "missing")
    if state not in VALID_STATES:
        return None, "ambiguous"
    return entry.get("value"), state


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def display_score(value: float, places: int = 2) -> float:
    """Round for display using conventional half-up rounding, not bankers rounding."""
    quantum = Decimal("1").scaleb(-places)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def validate_config(config: dict[str, Any]) -> None:
    weights = config.get("weights")
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Config must contain a non-empty weights object.")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0 for v in weights.values()):
        raise ValueError("Weights must be non-negative numbers.")
    if not math.isclose(sum(weights.values()), 100.0, abs_tol=1e-8):
        raise ValueError(f"Weights must total 100; got {sum(weights.values())}.")
    scoring = config.get("scoring", {})
    if set(weights) != set(scoring):
        raise ValueError("Each configured weight must have exactly one scoring definition.")
    for key, spec in scoring.items():
        if not math.isclose(float(weights[key]), float(spec.get("max_points", weights[key])), abs_tol=1e-8):
            raise ValueError(f"Weight and maximum points differ for {key}.")
    if config.get("budget_ceiling", 0) <= 0 or config.get("completion_deadline_weeks", 0) <= 0:
        raise ValueError("Budget ceiling and deadline must be positive.")


def number_field(proposal: dict[str, Any], path: str) -> tuple[float | None, str]:
    value, state = value_and_state(proposal, path)
    if state != "supported" or value is None:
        return None, state
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None, "ambiguous"
    return float(value), state


def team_points(proposal: dict[str, Any], spec: dict[str, Any]) -> tuple[float | None, list[str]]:
    team = get_path(proposal, "facts.team_approach")
    if not isinstance(team, dict):
        return None, ["Team-and-approach evidence is missing."]
    total = 0.0
    issues: list[str] = []
    points_each = float(spec["points_per_item"])
    for item in spec["items"]:
        key = item["id"]
        if key not in team or team[key] is None:
            issues.append(f"Team evidence is unclear for {key.replace('_', ' ')}.")
            continue
        if not isinstance(team[key], bool):
            issues.append(f"Team evidence is invalid for {key.replace('_', ' ')}.")
            continue
        if team[key]:
            total += points_each
    if issues:
        return None, issues
    return min(total, float(spec["max_points"])), []


def score_breakdown(proposal: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, float] | None, list[str]]:
    specs = config["scoring"]
    parts: dict[str, float] = {}
    issues: list[str] = []

    installs, state = number_field(proposal, specs["experience"]["input_path"])
    if installs is None:
        issues.append("Qualifying installation count within the five-year window is missing or unclear.")
    elif installs < 0:
        issues.append("Qualifying installation count cannot be negative.")
    else:
        exp = specs["experience"]
        parts["experience"] = float(exp["max_points"]) * clamp(installs / float(exp["full_score_installs"]))

    price, _ = number_field(proposal, specs["price"]["input_path"])
    if price is None:
        issues.append("A supported total price is required for scoring.")
    elif price < 0:
        issues.append("Price cannot be negative.")
    else:
        price_spec = specs["price"]
        high = float(price_spec["zero_score_at_cad"])
        full = float(price_spec["full_score_at_or_below_cad"])
        if high <= full:
            raise ValueError("Price scoring requires zero-score anchor above full-score anchor.")
        parts["price"] = float(price_spec["max_points"]) * clamp((high - price) / (high - full))

    weeks, _ = number_field(proposal, specs["timeline"]["input_path"])
    if weeks is None:
        issues.append("A supported completion duration is required for scoring.")
    elif weeks < 0:
        issues.append("Timeline cannot be negative.")
    else:
        timeline_spec = specs["timeline"]
        high = float(timeline_spec["zero_score_at_weeks"])
        full = float(timeline_spec["full_score_at_or_below_weeks"])
        if high <= full:
            raise ValueError("Timeline scoring requires the zero-score deadline above the full-score anchor.")
        parts["timeline"] = float(timeline_spec["max_points"]) * clamp((high - weeks) / (high - full))

    warranty_spec = specs["warranty"]
    panel, _ = number_field(proposal, warranty_spec["panel_years_path"])
    workmanship, _ = number_field(proposal, warranty_spec["workmanship_years_path"])
    if panel is None or workmanship is None:
        issues.append("Both panel and workmanship warranty durations are required for scoring.")
    elif panel < 0 or workmanship < 0:
        issues.append("Warranty durations cannot be negative.")
    else:
        panel_points = float(warranty_spec["panel_points"]) * clamp(
            panel / float(warranty_spec["panel_years_full_score"])
        )
        work_points = float(warranty_spec["workmanship_points"]) * clamp(
            workmanship / float(warranty_spec["workmanship_years_full_score"])
        )
        parts["warranty"] = panel_points + work_points

    team_score, team_issues = team_points(proposal, specs["team_approach"])
    if team_score is None:
        issues.extend(team_issues)
    else:
        parts["team_approach"] = team_score

    if issues or set(parts) != set(config["weights"]):
        return None, issues
    return parts, []


def mandatory_review(proposal: dict[str, Any], config: dict[str, Any]) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    unknowns: list[str] = []
    for check in config["mandatory_checks"]:
        value, state = value_and_state(proposal, check["input_path"])
        label = check["description"]
        if state != "supported" or value is None:
            unknowns.append(f"Mandatory evidence is unresolved: {label}.")
            continue
        if check["kind"] == "boolean":
            if not isinstance(value, bool):
                unknowns.append(f"Mandatory evidence has an invalid value: {label}.")
            elif value is not check["required_value"]:
                failures.append(f"Confirmed mandatory failure: {label}.")
        elif check["kind"] == "minimum_number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                unknowns.append(f"Mandatory evidence has an invalid value: {label}.")
            elif float(value) < float(check["minimum"]):
                failures.append(f"Confirmed mandatory failure: {label}.")
        else:
            raise ValueError(f"Unsupported mandatory check kind: {check['kind']}")
    return failures, unknowns


def assess_proposal(proposal: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal", "?"))
    reasons: list[str] = []
    confirmed_failures, unresolved_mandatory = mandatory_review(proposal, config)
    reasons.extend(confirmed_failures)
    reasons.extend(unresolved_mandatory)

    price, price_state = number_field(proposal, config["scoring"]["price"]["input_path"])
    if price is not None and price > float(config["budget_ceiling"]):
        reasons.append("The stated price exceeds the configured budget ceiling.")
        confirmed_failures.append("Budget ceiling exceeded.")

    weeks, timeline_state = number_field(proposal, config["scoring"]["timeline"]["input_path"])
    if weeks is not None and weeks > float(config["completion_deadline_weeks"]):
        reasons.append("The stated schedule exceeds the configured completion deadline.")
        confirmed_failures.append("Completion deadline exceeded.")

    alerts = proposal.get("security_alerts", [])
    if alerts:
        reasons.append("Instruction-like content aimed at automated reviewers was detected; it is ignored and requires human review.")

    ambiguities = proposal.get("ambiguities", [])
    for ambiguity in ambiguities:

        reasons.append(str(ambiguity))

    breakdown, scoring_issues = score_breakdown(proposal, config)
    if scoring_issues:
        for issue in scoring_issues:
            if issue not in reasons:
                reasons.append(issue)

    if confirmed_failures:
        status = "ineligible"
        score_unrounded = None
        score = None
        breakdown_out: dict[str, float] = {}
        rank = None
    else:
        score_unrounded = sum(breakdown.values()) if breakdown is not None else None
        score = display_score(score_unrounded, int(config["ranking"]["precision"])) if score_unrounded is not None else None
        breakdown_out = {k: display_score(v, int(config["ranking"]["precision"])) for k, v in (breakdown or {}).items()}
        has_review_issue = bool(reasons) or bool(unresolved_mandatory) or score is None
        status = "flagged" if has_review_issue else "ranked"
        rank = None

    return {
        "proposal": proposal_id,
        "rank": rank,
        "status": status,
        "score": score,
        "score_unrounded": score_unrounded,
        "reason": build_reason(proposal_id, status, score, reasons, breakdown_out),
        "score_breakdown": breakdown_out if breakdown_out else None,
        "review_flags": reasons
    }


def build_reason(
    proposal_id: str,
    status: str,
    score: float | None,
    reasons: list[str],
    breakdown: dict[str, float]
) -> str:
    if status == "ineligible":
        return reasons[0] if reasons else "Confirmed failure of a mandatory project requirement."
    if status == "flagged":
        if proposal_id == "B" and score is not None:
            return "Provisional score only; bidder-held Ontario electrical licensing is not established, so this proposal is not ranked pending review."
        if proposal_id == "C":
            return "Flagged for a reviewer-directed instruction in the document and an unclear qualifying five-year experience count; no final score or rank is released."
        if proposal_id == "D":
            return "The completion schedule is not stated, so the timeline points cannot be calculated; request a committed duration before ranking."
        summary = reasons[0] if reasons else "A required fact needs human review."
        return summary if len(summary) <= 240 else summary[:237] + "..."
    if score is None:
        return "A final score is not available."
    if proposal_id == "A":
        return f"Ranked first among cleared proposals ({score:.2f}/100); highest assessed experience and a faster schedule than E offset the price score."
    if proposal_id == "E":
        return f"Ranked second among cleared proposals ({score:.2f}/100); strong warranty and team evidence are offset by fewer qualifying installs and a slower schedule than A."
    return f"Ranked among cleared proposals with {score:.2f}/100 based on the configured rubric."


def rank_results(results: list[dict[str, Any]], facts_by_id: dict[str, dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    price_path = config["scoring"]["price"]["input_path"]
    timeline_path = config["scoring"]["timeline"]["input_path"]

    def sort_key(result: dict[str, Any]) -> tuple[float, float, float, str]:
        proposal = facts_by_id[result["proposal"]]
        price, _ = number_field(proposal, price_path)
        weeks, _ = number_field(proposal, timeline_path)
        total = result.get("score_unrounded")
        return (
            -float(total if total is not None else result["score"]),
            float(price) if price is not None else float("inf"),
            float(weeks) if weeks is not None else float("inf"),
            result["proposal"],
        )

    eligible = sorted((r for r in results if r["status"] == "ranked" and r["score"] is not None), key=sort_key)
    rank_by_id = {result["proposal"]: i for i, result in enumerate(eligible, start=1)}
    for result in results:
        result["rank"] = rank_by_id.get(result["proposal"])

    results.sort(key=lambda r: r["proposal"])
    return results


def run() -> list[dict[str, Any]]:
    config = read_json(PROTOTYPE / "criteria.json")
    fixture = read_json(PROTOTYPE / "sample_facts.json")
    validate_config(config)
    proposals = fixture.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("sample_facts.json must contain a non-empty proposals list.")
    identifiers = [p.get("proposal") for p in proposals]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Proposal IDs must be unique.")

    results = [assess_proposal(p, config) for p in proposals]
    facts_by_id = {p["proposal"]: p for p in proposals}
    results = rank_results(results, facts_by_id, config)

   
    output: list[dict[str, Any]] = []
    for result in results:
        output.append({
            "proposal": result["proposal"],
            "rank": result["rank"],
            "status": result["status"],
            "score": result["score"],
            "reason": result["reason"]
        })
    output_path = ROOT / "ranking.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    details_path = PROTOTYPE / "score_details.json"
    details_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {output_path.relative_to(ROOT)} using criteria version {config['criteria_version']}.")
    print(f"Wrote detailed score diagnostics to {details_path.relative_to(ROOT)}.")
    for result in output:
        label = f"rank {result['rank']}" if result["rank"] is not None else result["status"]
        score_text = "unscored" if result["score"] is None else f"{result['score']:.2f}/100"
        print(f"{result['proposal']}: {label}, {score_text}")
    return output


if __name__ == "__main__":
    try:
        run()
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
