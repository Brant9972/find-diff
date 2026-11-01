"""Offline regression tests for the t1500_ released-photo metadata audit."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "media_pipeline"))
from audit_expansion_release import BANKS, report


def q(ident, name, license_label, reviewed, photo="photos/x.jpg",
      source="https://example.org", artist="A"):
    return {"id": ident, "name": name, "photo": photo,
            "humanReviewed": reviewed,
            "attribution": {"license": license_label,
                            "source": source, "artist": artist}}


class ExpansionReleaseAuditTests(unittest.TestCase):
    def test_only_expansion_entries_and_all_banks(self):
        banks = {
            "questions.json": [q("s001", "Legacy", "CC0", True),
                               q("t1500_001", "Alice", "CC BY 4.0", True)],
            "actors.json": [q("t1500_001", "Alice", "Copyright retained", False),
                            q("t1500_002", "Bob", "CC0", False)],
            "variety.json": [q("t1500_003", "Carol", "CC BY-SA 3.0", True)],
        }
        r = report(banks)
        self.assertEqual(set(banks), set(BANKS))
        self.assertEqual(r["expansionEntries"], 4)
        self.assertEqual(r["expansionUniqueByCanonicalName"], 3)
        self.assertEqual(r["declaredOpenLicenseEntries"], 3)
        self.assertEqual(r["humanReviewedFlagEntries"], 2)
        self.assertEqual(r["bothMetadataFlagsEntries"], 2)
        self.assertEqual(r["missingDeclaredOpenLicenseEntries"], 1)
        self.assertEqual(r["missingHumanReviewFlagEntries"], 2)
        self.assertEqual(r["queue"][0]["name"], "Alice")
        self.assertTrue(all(not row["independentlyCertified"] for row in r["queue"]))
        self.assertTrue(all(not e["fiveStageAndRightsIndependentlyVerified"]
                            for row in r["queue"] for e in row["entries"]))
        self.assertEqual(report(banks, 1)["returnedPeople"], 1)
        self.assertEqual(report(banks, 0)["returnedPeople"], 0)

    def test_missing_provenance_is_not_certified(self):
        banks = {"questions.json": [q("t1500_1", "A", "CC BY 4.0", True,
                                      source="", artist="")],
                 "actors.json": [], "variety.json": []}
        r = report(banks)
        self.assertEqual(r["peopleWithAnyMetadataGap"], 1)
        self.assertIn("source_url_missing", r["queue"][0]["entries"][0]["metadataGaps"])
        self.assertIn("author_missing", r["queue"][0]["entries"][0]["metadataGaps"])

    def test_duplicate_id_and_missing_photo_fail_closed(self):
        item = q("t1500_1", "A", "CC0", True)
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            report({"questions.json": [item, item], "actors.json": [], "variety.json": []})
        with self.assertRaisesRegex(ValueError, "missing name/photo"):
            report({"questions.json": [{**item, "photo": ""}],
                    "actors.json": [], "variety.json": []})
        with self.assertRaises(ValueError):
            report({"questions.json": [], "actors.json": [], "variety.json": []}, -1)


if __name__ == "__main__":
    unittest.main()
