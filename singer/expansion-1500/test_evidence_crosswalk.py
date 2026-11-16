import unittest
from evidence_crosswalk import crosswalk

class CrosswalkTests(unittest.TestCase):
    def test_unblocked_exact_id_source_lead(self):
        plan = {"selectedNew": [{"name": "甲", "plannedQuestionId": "t1"}]}
        media = {"items": [{"questionId": "t1", "source": "https://commons.wikimedia.org/wiki/File:Test.jpg", "license": "CC BY 4.0"}]}
        row = crosswalk(plan, [], media)["candidates"][0]
        self.assertEqual(row["mediaLeadCount"], 1)
        self.assertTrue(row["existingMediaLeads"][0]["requiresFreshIdentityLicenseAndFiveStageReview"])
    def test_blocked_live_cannot_become_lead(self):
        plan = {"selectedNew": [{"name": "甲", "plannedQuestionId": "t1"}]}
        media = {"items": [{"questionId": "t1", "source": "https://example.org/image.jpg"}]}
        row = crosswalk(plan, [("questions.json", {"id": "live1", "name": "甲"})], media)["candidates"][0]
        self.assertEqual(row["status"], "BLOCK")
        self.assertEqual(row["mediaLeadCount"], 0)
    def test_no_substring_or_search_terms_as_evidence(self):
        plan = {"selectedNew": [{"name": "家家", "plannedQuestionId": "t2", "searchTerms": ["家家美食"]}]}
        media = {"items": [{"questionId": "t2", "source": "家家美食"}]}
        row = crosswalk(plan, [], media)["candidates"][0]
        self.assertEqual(row["mediaLeadCount"], 0)
    def test_wrong_id_does_not_join(self):
        plan = {"selectedNew": [{"name": "乙", "plannedQuestionId": "t3"}]}
        media = {"items": [{"questionId": "t4", "source": "https://example.org/other.jpg"}]}
        self.assertEqual(crosswalk(plan, [], media)["unblockedWithExistingMediaLeads"], 0)

if __name__ == "__main__":
    unittest.main()
