import unittest
from build_review_queue import review_queue

class ReviewQueueTests(unittest.TestCase):
    def test_live_and_internal_duplicates_are_blocked(self):
        live = [("actors.json", {"id": "live1", "name": "羅霈穎", "aliases": ["羅璧玲"]})]
        plan = {"selectedNew": [
            {"name": "羅璧玲", "plannedQuestionId": "a"},
            {"name": "新人甲", "plannedQuestionId": "b"},
            {"name": "新人甲", "plannedQuestionId": "c"},
            {"name": "新人乙", "plannedQuestionId": "b"},
        ]}
        rows = review_queue(plan, live)
        self.assertEqual([x["status"] for x in rows], [
            "BLOCK", "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW", "BLOCK", "BLOCK"
        ])
        self.assertIn("already_live", rows[0]["reasons"])
        self.assertIn("duplicate_in_plan", rows[2]["reasons"])
        self.assertIn("duplicate_in_plan", rows[3]["reasons"])

    def test_substring_is_not_identity(self):
        rows = review_queue({"selectedNew": [{"name": "家家", "plannedQuestionId": "a"}]},
                            [("questions.json", {"id": "x", "name": "家家美食"})])
        self.assertEqual(rows[0]["status"], "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW")

if __name__ == "__main__":
    unittest.main()
