"""Targeted source integrity checks; this is NOT a game photo approval."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import CuratedCommons


class HuangShaokuCuratedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        cls.person = next(p for p in plan["selectedNew"] if p["plannedQuestionId"] == "t1500_0108")

    def test_exact_source_matches_wikimedia_hash_and_person_caption(self):
        p = self.person
        self.assertEqual(p["name"], "黃少谷")
        self.assertEqual(p["wikidataId"], "Q28408495")
        self.assertEqual(p["reviewExactCommonsFiles"], ["黃少谷 20171015誠品唱談會.jpg"])
        candidates = list(CuratedCommons().search(p, None))
        self.assertEqual(len(candidates), 1)
        item = candidates[0]
        self.assertEqual(item["filename"], p["reviewExactCommonsFiles"][0])
        self.assertEqual(item["artist"], "Lidian192847")
        self.assertEqual(item["license"], "CC BY-SA 4.0")
        self.assertEqual(item["licenseUrl"], "https://creativecommons.org/licenses/by-sa/4.0/")
        self.assertFalse(item["identityEvidence"]["visualIdentityVerified"])
        self.assertTrue(item["identityEvidence"]["curatedOriginalMetadataOnly"])

    def test_rejected_stage_photo_is_excluded_and_game_is_unapproved(self):
        p = self.person
        self.assertIn("https://commons.wikimedia.org/wiki/File:Huang_Shao-gu.jpg", p["excludedPhotoSources"])
        self.assertEqual(p["photoStatus"], "not_prepared")
        self.assertEqual(p["qaStatus"], "not_releasable")
        self.assertFalse(p["imageVerification"]["finalCropReviewed"])
        self.assertFalse(p["imageVerification"]["rightsDocumented"])


if __name__ == "__main__":
    unittest.main()
