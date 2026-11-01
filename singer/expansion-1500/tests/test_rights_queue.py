"""Regression tests for non-certifying, non-mutating live rights triage."""
import copy
import sys
import unittest
from pathlib import Path

MEDIA = Path(__file__).resolve().parents[1] / "media_pipeline"
sys.path.insert(0, str(MEDIA))
from rights_queue import build_queue  # noqa: E402


def row(name, identifier, license="CC BY 4.0", human=True,
        source="https://commons.wikimedia.org/wiki/File:A.jpg", artist="Photographer"):
    return {"id": identifier, "name": name, "photo": f"photos/{identifier}.jpg", "humanReviewed": human,
            "attribution": {"license": license, "source": source, "artist": artist}}


class RightsQueueTest(unittest.TestCase):
    def test_duplicate_person_all_banks_must_pass_and_not_certified(self):
        banks = {"questions.json": [row("甲", "s1")],
                 "actors.json": [row("甲", "a1", license="Copyright retained", human=False),
                                 row("乙", "a2", human=False)],
                 "variety.json": [row("丙", "v1")]}
        snapshot = copy.deepcopy(banks)
        report = build_queue(banks)
        self.assertEqual(banks, snapshot)
        self.assertEqual(report["totalEntries"], 4)
        self.assertEqual(report["totalPeopleByCanonicalName"], 3)
        self.assertEqual(report["queue"][0]["name"], "甲")
        self.assertEqual(report["queue"][0]["bankEntryCount"], 2)
        self.assertFalse(report["queue"][0]["independentlyCertified"])
        self.assertEqual(report["queue"][0]["unlicensedMetadataEntries"], 1)
        self.assertEqual(report["entryMetadataGapCounts"]["human_review_flag_missing"], 2)
        self.assertTrue(all(e["independentIdentityRightsAndFiveStageReview"] == "not_established"
                            for p in report["queue"] for e in p["entries"]))

    def test_author_source_and_conservative_license(self):
        banks = {"questions.json": [row("A", "s1", license="CC BY 4.0, maybe", source="", artist="")],
                 "actors.json": [], "variety.json": []}
        report = build_queue(banks, limit=0)
        self.assertEqual(report["returnedPeople"], 0)
        self.assertEqual(report["totalPeopleByCanonicalName"], 1)
        self.assertEqual(report["entryMetadataGapCounts"], {
            "author_metadata_missing": 1, "no_declared_open_license": 1, "source_url_missing": 1})

    def test_reject_duplicate_ids_and_missing_name(self):
        banks = {"questions.json": [row("A", "s1"), row("B", "s1")],
                 "actors.json": [], "variety.json": []}
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            build_queue(banks)
        banks["questions.json"] = [row("", "s1")]
        with self.assertRaisesRegex(ValueError, "missing name"):
            build_queue(banks)

    def test_stable_order_and_bad_limit(self):
        banks = {"questions.json": [row("乙", "s2", human=False), row("甲", "s1", human=False)],
                 "actors.json": [], "variety.json": []}
        self.assertEqual([p["name"] for p in build_queue(banks)["queue"]], ["乙", "甲"])
        with self.assertRaises(ValueError):
            build_queue(banks, limit=-1)


    def test_same_photo_reused_in_two_banks_counts_one_evidence_unit(self):
        a = row("甲", "s1", license="Copyright retained", human=False)
        b = row("甲", "a1", license="Copyright retained", human=False)
        b["photo"] = a["photo"]
        banks = {"questions.json": [a], "actors.json": [b], "variety.json": []}
        report = build_queue(banks)
        self.assertEqual(report["totalEntries"], 2)
        self.assertEqual(report["distinctPhotoAssetUnits"], 1)
        self.assertEqual(report["reusedBankEntryReferences"], 1)
        person = report["queue"][0]
        self.assertEqual(person["priorityScore"], 120)
        self.assertEqual(person["unlicensedMetadataEntries"], 2)
        self.assertEqual(person["distinctPhotoAssetUnits"], 1)
        self.assertEqual(len(person["assetUnits"][0]["bankReferences"]), 2)
        self.assertFalse(person["assetUnits"][0]["independentlyCertified"])

    def test_distinct_photos_and_conflicting_rights_are_never_coalesced(self):
        a = row("甲", "s1", license="Copyright retained", human=False)
        b = row("甲", "a1", license="CC BY 4.0", human=True)
        b["photo"] = a["photo"]
        banks = {"questions.json": [a], "actors.json": [b], "variety.json": []}
        report = build_queue(banks)
        person = report["queue"][0]
        self.assertEqual(person["distinctPhotoAssetUnits"], 2)
        self.assertEqual(person["attributionConflictsForSamePhoto"], 1)
        self.assertEqual(report["peopleWithAttributionConflictsForSamePhoto"], 1)
        self.assertEqual(person["priorityScore"], 320)
        b["photo"] = "photos/different.jpg"
        report = build_queue(banks)
        self.assertEqual(report["queue"][0]["distinctPhotoAssetUnits"], 2)
        self.assertEqual(report["queue"][0]["attributionConflictsForSamePhoto"], 0)
        self.assertEqual(report["queue"][0]["priorityScore"], 120)


if __name__ == "__main__":
    unittest.main()
