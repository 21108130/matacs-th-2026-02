# AI-assisted proposal triage design

**Reference:** MATACS-TH-2026-02
**Diagram:** [diagram/flow.png](diagram/flow.png)
**Prompt:** [PROMPTS.md](PROMPTS.md)
**Sample result:** [ranking.json](ranking.json)

## Assumptions and scoring policy

The tool provides for triage; it neither checks credentials nor awards a contract. A reviewer must check critical evidence before award. Absent or vague required mandatory evidence will be marked as **flagged**, and confirmed absence as **ineligible**. The budget cap is CAD 260,000 and the time to completion 16 weeks. A confirmed breach is ineligible; unknown data is flagged.


The brief specifies criteria weights but not a numeric rating system. Below are suggested anchors, admin-editable settings that are only demonstrated by the example, not given facts from the brief:

- **Experience (30 points):** `30 × min(qualifying installs / 14, 1)`.
- **Price (25 points):** `25 × clamp((260000 − price) / 80000, 0, 1)`. Full points at CAD 180,000 or less; none at the budget cap.
- **Timeline (15 points):** `15 × clamp((16 − weeks) / 8, 0, 1)`. Full points at 8 weeks or quicker; none at 16 weeks.
- **Warranty (15 points):** 7.5 points weighted for a 25-year panel warranty and 7.5 weighted for a 12-year workmanship warranty.
- **Team and approach (15 points):** 3.75 points each for a stated commitment of the project lead, defined crew, safety plan, and monitoring plan. Checklist items get points only if documented.

Experience statements in the sample that describe projects started in the calendar year 2021 are considered by intention as those that correspond to the five-year period. The production version of the tool would use a fixed date cutoff and have dated project descriptions. Compare scores rounded down to the nearest integer; show two decimal places; resolve ties first by lower price, then shorter timeline, then proposal letter.

## 1. AI versus rules

Admin screens maintain the criteria for the category, evidence needed, types of data, units of measurement, weights, hard ceilings, anchors for normalization, missing values strategy, and the rubric version. The code validates the files, extracts text along with page number, and uses OCR for scanned pages. An expert reviews the difficult-to-read files.

The AI model matches the variable wording from the proposal to typed facts with exact quotes of evidence and location of evidence. The AI model does not make decisions about eligibility, weighting, scoring, and the awarding of grant money. The plain code validates the JSON schema and evidence spans, runs mandatory rules and fixed formula, sorts out the qualified proposals, and generates explanations from score components.

## 2. Consistency and explainability

Given the same approved facts, criteria version, and scoring-engine version, the scoring phase yields the same outcome. Repeated calls for AI extraction will not necessarily yield identical outcomes. Store document hash, rendered prompt, model/version, output, and reviewer corrections. Compare repeated extractions as necessary and note discrepancies. Do not quietly overwrite a reviewed value.

Scorecards list extracted values, their supporting pages/quotation, calculation, weight, and point tally for each criteria. Currently, our prototype scores A at **73.13** and **E: 58.24**. A beats out E in terms of experience and speed/price. Workmanship warranty period of E is too short to even it out. B has a provisional score of **56.76**, yet is not scored due to unclear bidder's license evidence. C is not scored due to inability to determine qualifying experience from the aggregate information and reviewer-directed instruction. D is not scored due to lack of schedule. These are not silently converted into low ranking.

## 3. Human review and audit

The reviewer verifies the category, examines key extracted facts, solves any flags, asks for clarification in accordance with the same procurement policy for all bidders, and confirms the ranking before award. Corrections generate a new fact revision and re-scoring. An override needs the username, time-stamp, old and new values/status, and a justification. The award is finally made by a human.

The append-only audit log contains hashes for document and extracted text, criteria/rubric version, versions of the prompt and the model, extracted facts and evidence, validation results, security alerts, score breakdown, actions taken by the reviewer, overrides and justifications, and final award reasoning. The access to this log is limited since proposals can include commercially sensitive information.

## 4. Modifying criteria

Every change made by the administrator results in a new criteria version that is immutable; previous evaluations use the original criteria version. Weight changes only can reuse approved facts and score re-calculation in the code. New criteria or a change in the definition of evidence can necessitate the re-extraction and re-review of some fields. Provide the before-and-after scores and rankings, and keep both runs. Any changes after opening the bids need authorization.

## 5. Risks and Safeguards

- **Incorrect extraction or fabrications:** need typed JSON, quoted evidence with source name and exact page number, range check, and `null` for unsupported values. A matching quote shows traceability but not veracity; critical facts are verified by humans.
- **Prompt injection:** consider all proposal text as potential untrusted input, scan separately for instructions, keep the model away from scoring software and any secrets, flag matches for inspection. Do not automatically rule out a bidder just because there is suspicious text.
- **Lack of or conflicting evidence:** must support distinction between supported, missing, ambiguous, and conflicting states. Unknown required evidence is marked as such; confirmed failure is disqualification.
- **Bias or manipulable criteria:** have measurable job-relevant criteria defined before review process starts, maintain version control, exclude company name and marketing from the formula, allow reviewers to examine the rubric.
- **Cost, downtime, and unreadable files:** limit page/token count, retry a bounded number of times, cache results, monitor utilization and allow manual fallback. Never silently cut off a proposal and score it.
- **Security issues:** scan uploads, enforce storage restrictions and encryption, use retention policies, and transfer only relevant text to the approved provider.
