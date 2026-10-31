"""Exact-source and negative visual-screening regression; no game release."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import CuratedCommons


class SunYuehSourceScreeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        cls.people = {p["plannedQuestionId"]: p for p in plan["selectedNew"]}

    def test_sunyueh_exact_source_is_licensed_but_not_approved(self):
        person = self.people["t1500_0207"]
        self.assertEqual(person["name"], "孫越")
        self.assertEqual(person["wikidataId"], "Q9041952")
        self.assertIn("Yueh Sun", person["aliases"])
        self.assertEqual(person["photoStatus"], "not_prepared")
        self.assertFalse(person["imageVerification"]["finalCropReviewed"])
        self.assertEqual(person["qaStatus"], "not_releasable")
        candidates = list(CuratedCommons().search(person, None))
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["filename"], "2011 SKL RunUp Yueh Sun.jpg")
        self.assertEqual(candidate["artist"], "Rico Shen")
        self.assertEqual(candidate["license"], "CC BY-SA 4.0")
        self.assertTrue(candidate["identityEvidence"]["curatedOriginalMetadataOnly"])
        self.assertFalse(candidate["identityEvidence"]["visualIdentityVerified"])

    def test_two_bad_sources_remain_excluded(self):
        self.assertIn("https://commons.wikimedia.org/wiki/File:Rhydian-Vaughan.jpg",
                      self.people["t1500_0174"]["excludedPhotoSources"])
        self.assertIn("https://commons.wikimedia.org/wiki/File:TaLu.jpg",
                      self.people["t1500_0181"]["excludedPhotoSources"])
        for pid in ("t1500_0174", "t1500_0181"):
            self.assertNotEqual(self.people[pid]["photoStatus"], "published")
            self.assertFalse(self.people[pid]["imageVerification"]["finalCropReviewed"])


if __name__ == "__main__":
    unittest.main()
