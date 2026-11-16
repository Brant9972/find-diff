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
        by_name_id = {(x["name"], x["id"]): x for x in rows}
        self.assertIn("already_live", by_name_id[("羅璧玲", "a")]["reasons"])
        self.assertIn("duplicate_in_plan", by_name_id[("新人甲", "c")]["reasons"])
        self.assertIn("duplicate_in_plan", by_name_id[("新人乙", "b")]["reasons"])
        self.assertEqual(rows[0]["status"], "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW")

    def test_substring_is_not_identity(self):
        rows = review_queue({"selectedNew": [{"name": "家家", "plannedQuestionId": "a"}]},
                            [("questions.json", {"id": "x", "name": "家家美食"})])
        self.assertEqual(rows[0]["status"], "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW")

    def test_documented_source_first_but_never_approved(self):
        plan = {"selectedNew": [
            {"name": "無來源", "plannedQuestionId": "a", "priority": "A",
             "photoSearchKeywords": ["肖像"], "imageVerification": {"rightsDocumented": True}},
            {"name": "有來源", "plannedQuestionId": "b", "priority": "B",
             "portraitSource": "https://commons.wikimedia.org/wiki/File:Example.jpg",
             "rightsNote": "CC BY-SA 4.0", "imageVerification": {"rightsDocumented": True}},
        ]}
        rows = review_queue(plan, [])
        self.assertEqual(rows[0]["name"], "有來源")
        self.assertEqual(rows[0]["evidenceScore"], 2)
        self.assertFalse(rows[1]["evidence"]["rightsDocumented"])
        self.assertTrue(all(r["status"] == "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW" for r in rows))

    def test_blocked_evidence_does_not_displace_new_candidate(self):
        rows = review_queue({"selectedNew": [
            {"name": "羅璧玲", "plannedQuestionId": "a", "portraitSource": "https://example.org/image",
             "rightsNote": "CC BY", "imageVerification": {"rightsDocumented": True}},
            {"name": "新人", "plannedQuestionId": "b"}
        ]}, [("variety.json", {"name": "羅霈穎", "aliases": ["羅璧玲"]})])
        self.assertEqual(rows[0]["name"], "新人")
        self.assertEqual(rows[-1]["status"], "BLOCK")

if __name__ == "__main__":
    unittest.main()
