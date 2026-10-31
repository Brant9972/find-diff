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
        self.assertEqual(person["reviewExactCommonsFiles"],
                         ["Liuhsiufu2023.png", "Liuhsiufu2020.png"])
        self.assertEqual(person["photoStatus"], "not_prepared")
        self.assertEqual(person["qaStatus"], "not_releasable")
        self.assertFalse(person["imageVerification"]["rightsDocumented"])
        self.assertFalse(person["imageVerification"]["finalCropReviewed"])
        self.assertEqual(person["hintsStatus"], "candidate_only_unverified")

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
