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
    def test_rejected_sources_are_not_recycled(self):
        plan = {"selectedNew": [{"name": "瑪莎", "plannedQuestionId": "t1500_0169"}]}
        media = {"items": [
            {"questionId": "t1500_0169", "source": "https://example.org/old.jpg",
             "reviewStatus": "rejected_previous_source_identity_conflict"},
            {"questionId": "t1500_0169", "source": "https://example.org/blurry.jpg",
             "reviewStatus": "rejected_blurry_branded_image"},
            {"questionId": "t1500_0169", "source": "https://example.org/eyes.jpg",
             "reviewStatus": "rejected_eyes_not_visible"},
            {"questionId": "t1500_0169", "source": "https://example.org/alternative.jpg",
             "reviewStatus": "needs_alternative_source"},
        ]}
        row = crosswalk(plan, [], media)["candidates"][0]
        self.assertEqual(row["mediaLeadCount"], 0)

    def test_valid_source_survives_rejected_source_for_same_person(self):
        plan = {"selectedNew": [{"name": "甲", "plannedQuestionId": "t1"}]}
        media = {"items": [
            {"questionId": "t1", "source": "https://example.org/rejected.jpg",
             "reviewStatus": "rejected_eyes_not_visible"},
            {"questionId": "t1", "source": "https://commons.wikimedia.org/wiki/File:Good.jpg",
             "reviewStatus": "pending_review"},
        ]}
        row = crosswalk(plan, [], media)["candidates"][0]
        self.assertEqual(row["mediaLeadCount"], 1)
        self.assertIn("Good.jpg", row["existingMediaLeads"][0]["source"])

    def test_known_teresa_teng_photo_cannot_be_used_for_liu_jia_chang(self):
        plan = {"selectedNew": [{"name": "劉家昌", "plannedQuestionId": "t1500_0465"}]}
        media = {"items": [
            {"questionId": "t1500_0465", "source": "https://commons.wikimedia.org/wiki/File:Teresa_Teng_onstage.jpg", "reviewStatus": "draft_not_verified"},
            {"questionId": "t1500_0465", "source": "https://commons.wikimedia.org/wiki/File:Different_verified_candidate.jpg", "reviewStatus": "pending_review"},
        ]}
        row = crosswalk(plan, [], media)["candidates"][0]
        self.assertEqual(row["mediaLeadCount"], 1)
        self.assertIn("Different_verified_candidate.jpg", row["existingMediaLeads"][0]["source"])

    def test_wrong_id_does_not_join(self):
        plan = {"selectedNew": [{"name": "乙", "plannedQuestionId": "t3"}]}
        media = {"items": [{"questionId": "t4", "source": "https://example.org/other.jpg"}]}
        self.assertEqual(crosswalk(plan, [], media)["unblockedWithExistingMediaLeads"], 0)

if __name__ == "__main__":
    unittest.main()
