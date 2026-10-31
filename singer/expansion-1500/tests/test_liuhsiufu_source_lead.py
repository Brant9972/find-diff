"""Liu Hsiu-fu's source leads are not image approvals; protect verified work hint."""
import json
import unittest
from pathlib import Path


class LiuHsiufuSourceLeadTest(unittest.TestCase):
    def test_correct_person_work_and_photo_source_gate(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / "release-plan-20261028.json").read_text(encoding="utf-8"))
        rows = [row for row in plan["selectedNew"] if row["plannedQuestionId"] == "t1500_0312"]
        self.assertEqual(len(rows), 1)
        person = rows[0]
        self.assertEqual(person["name"], "劉修甫")
        self.assertEqual(person["proposedPrimaryBank"], "actors.json")
        self.assertIn("你的孩子不是你的孩子", person["representativeWorks"])
        self.assertNotIn("誰是被害者", person["representativeWorks"])
        self.assertEqual(person["verifiedWorkSources"][0]["url"],
                         "https://about.pts.org.tw/pr/latestnews/article/3816")
        self.assertEqual(person["reviewExactCommonsFiles"], [])
        self.assertEqual(set(person["excludedPhotoSources"]), {
            "https://commons.wikimedia.org/wiki/File:Liuhsiufu2023.png",
            "https://commons.wikimedia.org/wiki/File:Liuhsiufu2020.png",
        })
        self.assertEqual(person["photoSourceRightsStatus"],
                         "BLOCKED_EXACT_TWO_COMMONS_LICENSE_REVIEW_NEEDED")
        self.assertEqual(person["photoStatus"], "not_prepared")
        self.assertEqual(person["qaStatus"], "not_releasable")
        self.assertFalse(person["imageVerification"]["rightsDocumented"])
        self.assertFalse(person["imageVerification"]["finalCropReviewed"])
        self.assertEqual(person["hintsStatus"], "candidate_only_unverified")

    def test_rejected_rights_are_not_approvals(self):
        root = Path(__file__).resolve().parents[1]
        review = json.loads((root / "pipeline/chatgpt-review/20261031-liuhsiufu-license-source-rejected.json").read_text(encoding="utf-8"))
        self.assertEqual(review["releaseGate"], "REJECTED_EXACT_SOURCES_NOT_PLAYABLE")
        self.assertEqual(review["sourceDiagnostic"]["metadataCandidates"], 2)
        self.assertEqual(review["sourceDiagnostic"]["openLicenseMetadata"], 0)
        self.assertFalse(review["imagePixelInspected"])
        self.assertFalse(review["gameCropReviewed"])
        self.assertFalse(review["fiveStageReviewed"])
        self.assertFalse(review["approvedForLive"])
        for source in review["sourcePages"]:
            self.assertEqual(source["commonsCategory"], "License review needed")
            self.assertFalse(source["commonsReviewed"])
            self.assertTrue(source["decision"].startswith("BLOCK_EXACT_SOURCE"))

    def test_not_already_live_under_known_name(self):
        root = Path(__file__).resolve().parents[2]
        names = {"劉修甫", "刘修甫", "Liu Hsiu-fu", "Liu Hsiu Fu"}
        for bank in ("questions.json", "actors.json", "variety.json"):
            questions = json.loads((root / bank).read_text(encoding="utf-8"))["questions"]
            for question in questions:
                self.assertFalse(names.intersection({question["name"], *question.get("aliases", [])}),
                                 f"Person already live in {bank}: {question['id']}")


if __name__ == "__main__":
    unittest.main()
