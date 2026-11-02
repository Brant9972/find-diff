"""Validate the immutable, non-certifying main 9a30e9cf rights audit snapshot.

This snapshot is not a source of legal permission and must never promote
existing live photographs to approved status.
"""
import json
import unittest
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / "pipeline" / "20261102-main-9a30e9cf-legacy-rights-queue.json"


class LegacyRightsSnapshotTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_baseline_and_release_guard(self):
        d = self.data
        self.assertEqual(d["baselineMainSha"], "9a30e9cf333a063efa946bf6b481e61634f5c45a")
        self.assertEqual(d["releaseGate"], "AUDIT_ONLY_NOT_RELEASE_APPROVAL")
        self.assertIn("NOT", d["warning"])

    def test_totals_and_cross_bank_deduplication(self):
        d = self.data
        summary = d["summary"]
        self.assertEqual(sum(summary["banks"].values()), summary["entries"])
        self.assertEqual(summary["entries"], 1146)
        self.assertEqual(summary["uniquePeopleByCanonicalName"], 1078)
        self.assertEqual(summary["crossBankExtraEntries"], 68)
        self.assertEqual(summary["declaredOpenLicenseEntries"] + summary["noDeclaredOpenLicenseEntries"], summary["entries"])
        self.assertEqual(summary["noDeclaredOpenLicenseEntries"], 587)
        self.assertEqual(summary["uniquePeopleWithNoDeclaredOpenLicense"], 575)
        self.assertEqual(summary["uniquePeopleWithNoDeclaredOpenLicense"], len(d["rightsUnresolved"]))
        self.assertEqual(sum(len(p["bankReferences"]) for p in d["rightsUnresolved"]), 587)

    def test_no_unverified_rights_are_marked_approved(self):
        d = self.data
        names = set()
        bank_ids = set()
        for person in d["rightsUnresolved"]:
            self.assertNotIn(person["name"], names)
            names.add(person["name"])
            self.assertIs(person["independentlyCertified"], False)
            for entry in person["bankReferences"]:
                key = (entry["bank"], entry["id"])
                self.assertNotIn(key, bank_ids)
                bank_ids.add(key)
                self.assertIn(entry["bank"], d["summary"]["banks"])
                self.assertTrue(entry["photo"].startswith("photos/"))
                self.assertTrue(entry["source"].startswith("http"))
                self.assertIn("Copyright retained", entry["license"])
                self.assertEqual(entry["licenseUrl"], "")
        self.assertEqual(len(bank_ids), 587)
        self.assertEqual(sum(not e["humanReviewedFlag"] for p in d["rightsUnresolved"]
                             for e in p["bankReferences"]), 2)


if __name__ == "__main__":
    unittest.main()
