"""Keep eight retained-source visual decisions and six exact-source exclusions stable."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "pipeline/chatgpt-review/20261101-retained-source-eight-screening.json"

class RetainedEightVisualReviewTest(unittest.TestCase):
    def test_six_rejections_are_exact_and_do_not_remove_people(self):
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        people = {p["plannedQuestionId"]: p for p in plan["selectedNew"]}
        self.assertEqual(audit["releaseGate"], "DRAFT_ONLY_NOT_PLAYABLE")
        self.assertEqual(audit["summary"]["retainedSourcesReviewed"], 8)
        self.assertEqual(audit["summary"]["exactSourcesRejected"], 6)
        self.assertEqual(audit["summary"]["pendingIndependentReview"], 2)
        self.assertEqual(audit["summary"]["approvedForGame"], 0)
        self.assertEqual(len(audit["decisions"]), 8)
        for item in audit["decisions"]:
            self.assertIn(item["personId"], people)
            self.assertFalse(item["eligibleForLive"])
            self.assertEqual(people[item["personId"]]["photoStatus"], "not_prepared")
            if item["decision"] == "reject_exact_source":
                self.assertIn(item["sourcePage"], people[item["personId"]]["excludedPhotoSources"])
            else:
                self.assertNotIn(item["sourcePage"], people[item["personId"]].get("excludedPhotoSources", []))
        self.assertEqual({x["personId"] for x in audit["decisions"] if x["decision"] != "reject_exact_source"}, {"t1500_0123", "t1500_0171"})

    def test_chen_shiang_chyi_five_stages_are_not_rights_approval(self):
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        row = next(x for x in audit["decisions"] if x["personId"] == "t1500_0171")
        self.assertEqual(row["decision"], "pending_rights_and_crop")
        self.assertEqual(row["gameSha256"], "f186fd95e6ed3d7592fd3a0ceba6f51d74f5fb04e455f7c4ba47a88a24562fb4")
        self.assertIn("independently verified", row["rights"])
        self.assertFalse(row["eligibleForLive"])

if __name__ == "__main__":
    unittest.main()
