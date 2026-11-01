"""Keep independently checked 2026-11-01 source follow-up draft-only."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "pipeline/chatgpt-review/20261101-nolay-chen-independent-source-followup.json"


class IndependentSourceFollowupTest(unittest.TestCase):
    def test_identity_and_rights_holds_cannot_be_counted_as_release(self):
        data = json.loads(REVIEW.read_text(encoding="utf-8"))
        self.assertEqual(data["releaseGate"], "DRAFT_ONLY_NOT_PLAYABLE")
        self.assertEqual(data["summary"]["newGameCropsApproved"], 0)
        self.assertEqual(data["summary"]["productionChanges"], 0)
        self.assertEqual(len(data["decisions"]), 3)
        self.assertTrue(all(not row["eligibleForLive"] for row in data["decisions"]))
        self.assertEqual(
            [row["personId"] for row in data["decisions"]],
            ["t1500_0123", "t1500_0123", "t1500_0171"],
        )
        self.assertEqual(data["decisions"][0]["decision"],
                         "pending_manual_isolation_and_full_pixel_review")
        self.assertEqual(data["decisions"][0]["wikidataQid"], "Q7224941")
        self.assertEqual(data["decisions"][1]["decision"], "reject_exact_source_game_crop")
        self.assertEqual(data["decisions"][1]["licenseReview"],
                         "Leoboudv verified Flickr license on 2013-11-08")
        self.assertEqual(data["decisions"][2]["decision"], "continue_rights_hold")
        self.assertIn("could not be fetched", data["decisions"][2]["rightsEvidence"])


if __name__ == "__main__":
    unittest.main()
