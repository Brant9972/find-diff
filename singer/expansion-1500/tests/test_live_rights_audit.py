import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.audit_live import BANKS, audit, open_license


def person(name, license_label, reviewed):
    return {
        "name": name,
        "humanReviewed": reviewed,
        "attribution": {"license": license_label},
    }


class LiveRightsAuditTest(unittest.TestCase):
    def test_declared_open_license_is_conservative(self):
        self.assertTrue(open_license(person("A", "CC BY-SA 4.0", True)))
        self.assertTrue(open_license(person("A", "CC BY 2.5", True)))
        self.assertFalse(open_license(person("A", "CC BY-SA 99.0", True)))
        self.assertFalse(open_license(person("A", "CC BY 0.1", True)))
        self.assertTrue(open_license(person("A", "CC0", True)))
        self.assertTrue(open_license(person("A", "PD", True)))
        self.assertFalse(open_license(person("A", "Copyright retained by original source; no open licence asserted", True)))
        self.assertFalse(open_license(person("A", "CC BY-SA 4.0 (unverified)", True)))
        self.assertFalse(open_license({"name": "A", "attribution": {}}))

    def test_cross_bank_duplicates_require_every_photo_to_pass_metadata(self):
        banks = {
            "questions.json": [
                person("Alice", "CC BY 4.0", True),
                person("Bob", "Copyright retained by original source; no open licence asserted", True),
            ],
            "actors.json": [
                person("Alice", "CC BY-SA 4.0", False),
                person("Carol", "CC0", True),
            ],
            "variety.json": [person("Dana", "", False)],
        }
        report = audit(banks)
        self.assertEqual(set(report["banks"]), set(BANKS))
        self.assertEqual(report["entries"]["entries"], 5)
        self.assertEqual(report["entries"]["declaredOpenLicense"], 3)
        self.assertEqual(report["entries"]["humanReviewedFlag"], 3)
        self.assertEqual(report["entries"]["bothMetadataFlags"], 2)
        self.assertEqual(report["entries"]["noDeclaredOpenLicense"], 2)
        self.assertEqual(report["entries"]["openButNoHumanFlag"], 1)
        self.assertEqual(report["entries"]["humanFlagButNoOpen"], 1)
        people = report["uniqueByCanonicalName"]
        self.assertEqual(people["playableNames"], 4)
        self.assertEqual(people["crossBankExtraEntries"], 1)
        self.assertEqual(people["allEntriesDeclaredOpen"], 2)
        self.assertEqual(people["noEntriesDeclaredOpen"], 2)
        self.assertEqual(people["allEntriesHumanReviewedFlag"], 2)
        self.assertEqual(people["noEntriesHumanReviewedFlag"], 1)
        self.assertEqual(people["allEntriesBothMetadataFlags"], 1)
        self.assertIn("not", report["warning"])

    def test_empty_name_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing canonical name"):
            audit({"questions.json": [person("", "CC0", True)],
                   "actors.json": [], "variety.json": []})


if __name__ == "__main__":
    unittest.main()
