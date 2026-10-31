"""Prevent rejected exact-source P18 photos from being treated as approved game portraits."""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExactP18ThreeSourceReviewTest(unittest.TestCase):
    def test_only_existing_selected_new_and_correct_qids(self):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        people = {row["plannedQuestionId"]: row for row in plan["selectedNew"]}
        expected = {
            "t1500_0457": ("王耀慶", "Q9315976", "王耀慶@2011.jpg"),
            "t1500_0562": ("張達明", "Q5094266", "張達明.jpg"),
            "t1500_0583": ("江華", "Q5692593", "江華.jpg"),
        }
        for person_id, (name, qid, filename) in expected.items():
            with self.subTest(person_id=person_id):
                person = people[person_id]
                self.assertEqual(person["name"], name)
                self.assertEqual(person["wikidataId"], qid)
                self.assertIn(filename, person["reviewExactCommonsFiles"])
                if person_id == "t1500_0562":
                    # This candidate passed a later independent crop/rights
                    # review; the old source-only report remains unchanged.
                    self.assertEqual(person["photoStatus"], "published")
                    self.assertTrue(person["imageVerification"]["finalCropReviewed"])
                else:
                    self.assertNotEqual(person["photoStatus"], "published")
                    self.assertFalse(person["imageVerification"]["finalCropReviewed"])

    def test_visually_rejected_sources_are_excluded_without_excluding_people(self):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        people = {row["plannedQuestionId"]: row for row in plan["selectedNew"]}
        for person_id, url in (
            ("t1500_0457", "https://commons.wikimedia.org/wiki/File:王耀慶@2011.jpg"),
            ("t1500_0583", "https://commons.wikimedia.org/wiki/File:江華.jpg"),
        ):
            self.assertIn(url, people[person_id]["excludedPhotoSources"])
        self.assertNotIn(
            "https://commons.wikimedia.org/wiki/File:張達明.jpg",
            people["t1500_0562"].get("excludedPhotoSources", []),
        )

    def test_source_review_cannot_be_mistaken_for_five_stage_approval(self):
        report = json.loads(
            (ROOT / "pipeline" / "chatgpt-review" /
             "20261031-three-p18-original-visual-screening.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["releaseGate"], "SOURCE_SCREENING_ONLY_NOT_PLAYABLE")
        self.assertEqual(len(report["records"]), 3)
        self.assertTrue(all(not row["approvedForLive"] for row in report["records"]))
        self.assertTrue(all(not row["fiveStageReviewed"] for row in report["records"]))
        by_id = {row["personId"]: row for row in report["records"]}
        self.assertEqual(by_id["t1500_0562"]["representativeWork"], "大內密探零零發")
        self.assertIn("tv.apple.com", by_id["t1500_0562"]["workEvidenceUrl"])
        self.assertEqual(
            by_id["t1500_0562"]["decision"], "source_only_visual_candidate_pending_game_crop"
        )


if __name__ == "__main__":
    unittest.main()
