import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

import score 


class ScoringPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = score.read_json(ROOT / "prototype" / "criteria.json")
        cls.fixture = score.read_json(ROOT / "prototype" / "sample_facts.json")

    def test_weights_total_100(self):
        score.validate_config(self.config)
        self.assertEqual(sum(self.config["weights"].values()), 100)

    def test_sample_rankings_and_statuses(self):
        results = score.run()
        by_id = {row["proposal"]: row for row in results}
        self.assertEqual(by_id["A"]["rank"], 1)
        self.assertAlmostEqual(by_id["A"]["score"], 73.13)
        self.assertEqual(by_id["E"]["rank"], 2)
        self.assertAlmostEqual(by_id["E"]["score"], 58.24)
        self.assertEqual(by_id["B"]["status"], "flagged")
        self.assertIsNone(by_id["B"]["rank"])
        self.assertAlmostEqual(by_id["B"]["score"], 56.76)
        self.assertEqual(by_id["C"]["status"], "flagged")
        self.assertIsNone(by_id["C"]["rank"])
        self.assertIsNone(by_id["C"]["score"])
        self.assertEqual(by_id["D"]["status"], "flagged")
        self.assertIsNone(by_id["D"]["rank"])
        self.assertIsNone(by_id["D"]["score"])
        expected_keys = {"proposal", "rank", "status", "score", "reason"}
        output_json = json.loads((ROOT / "ranking.json").read_text(encoding="utf-8"))
        self.assertTrue(all(set(row) == expected_keys for row in output_json))
        details = json.loads((ROOT / "prototype" / "score_details.json").read_text(encoding="utf-8"))
        self.assertIn("score_breakdown", details[0])

    def test_confirmed_mandatory_failure_is_ineligible(self):
        proposal = json.loads(json.dumps(self.fixture["proposals"][0]))
        proposal["mandatory"]["electrical_licence_held_by_bidder"] = {
            "value": False,
            "state": "supported"
        }
        result = score.assess_proposal(proposal, self.config)
        self.assertEqual(result["status"], "ineligible")
        self.assertIsNone(result["rank"])
        self.assertIsNone(result["score"])

    def test_unknown_mandatory_evidence_flags_not_fails(self):
        proposal = json.loads(json.dumps(self.fixture["proposals"][0]))
        proposal["mandatory"]["electrical_licence_held_by_bidder"] = {
            "value": None,
            "state": "missing"
        }
        result = score.assess_proposal(proposal, self.config)
        self.assertEqual(result["status"], "flagged")
        self.assertIsNone(result["rank"])

    def test_same_fixture_is_deterministic(self):
        first = score.run()
        second = score.run()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
