"""Previously human-rejected source pixels must not reappear in review exports.

Keep each exact Commons file rejected for that person only. Other photographs
and the existing selectedNew person remain eligible for review.
"""
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import source_key, excluded_commons_keys

# Exact retained-source filenames from 2026-10-30/31 visual review evidence.
REJECTED = {
    "t1500_0333": "HK CWB 銅鑼灣 Causeway Bay 糖街 Sugar Street July 2018 SSG construction site n minibus public light bus strand 01.jpg",
    "t1500_0376": "A-vai Tzeng 20101029.jpg",
    "t1500_0390": "HK WTS 黃大仙 Wong Tai Sin 雙鳳街 Sheung Fung Street shop 家家美食 Ka Ka Cuisine Restaurant food September 2021 SS2 04.jpg",
    "t1500_0392": "Guanyuchen&Ilid-Kaolo.jpg",
    "t1500_0394": "2024 黃玠瑋 Zooey Wonder ＠The Wall Taipei.jpg",
    "t1500_0551": "HK MTR passageway poster film 源生罪 Deliverance by 岑嘉彥、黃永峯，任達華、曾江、鮑起靜、吳婉儀、吳家麗、吳卓羲、陳紫萱、張建聲、郭奕芯、岑珈其 January 2024 R12S.jpg",
    "t1500_0565": "Michael Tse close up.jpg",
    "t1500_0568": "Lee Sze Kei 2.JPG",
}


class RetainedRejectionSyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / "release-plan-20261028.json").read_text(encoding="utf-8"))
        cls.people = {p["plannedQuestionId"]: p for p in plan["selectedNew"]}

    def test_exact_rejected_sources_are_excluded_for_their_person(self):
        for pid, filename in REJECTED.items():
            with self.subTest(pid=pid):
                person = self.people[pid]
                expected = source_key("https://commons.wikimedia.org/wiki/File:" + quote(filename.replace(" ", "_")))
                self.assertIn(expected, excluded_commons_keys(person))
                self.assertNotEqual(person.get("photoStatus"), "published")
                self.assertFalse(person["imageVerification"]["finalCropReviewed"])

    def test_source_specific_not_global_person_ban(self):
        # No rejection can remove the person, their other sources, or creators.
        for pid, filename in REJECTED.items():
            with self.subTest(pid=pid):
                person = self.people[pid]
                self.assertEqual(person["plannedQuestionId"], pid)
                self.assertTrue(person["name"])
                excluded = excluded_commons_keys(person)
                unrelated = source_key("https://commons.wikimedia.org/wiki/File:Different_licensed_portrait_" + pid + ".jpg")
                self.assertNotIn(unrelated, excluded)
        # Regression: 家家 is not the Hong Kong restaurant, 黃玠 is not 黃玠瑋.
        self.assertEqual(self.people["t1500_0390"]["name"], "家家")
        self.assertEqual(self.people["t1500_0394"]["name"], "黃玠")


if __name__ == "__main__":
    unittest.main()
