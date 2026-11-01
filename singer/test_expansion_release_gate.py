"""Regression tests for non-retroactive expansion release protection."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from qa_expansion_release_gate import validate, snapshot, license_ok, verify_reveal, BANKS

SHA = "a" * 40


def person(pid="t1500_0001"):
    return {
        "id": pid, "name": "測試歌手", "photo": f"photos/{pid}.jpg",
        "photoStatus": "reviewed", "eligibility": "approved",
        "humanReviewed": True,
        "attribution": {"source": "https://commons.wikimedia.org/wiki/File:Test.jpg",
                        "artist": "Photographer", "license": "CC BY-SA 4.0",
                        "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/"},
        "reveal": {"eyes": [0.08, .3, .92, .4],
                   "nose": [0.08, .3, .92, .5],
                   "mouth": [0.08, .3, .92, .6],
                   "chin": [0.08, .3, .92, .8],
                   "full": [0, 0, 1, 1]},
    }


class ExpansionGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "photos").mkdir()
        self.row = person()
        content = b"test jpeg bytes"
        (self.root / self.row["photo"]).write_bytes(content)
        self.row["gameSha256"] = hashlib.sha256(content).hexdigest()
        self.banks = {b: [] for b in BANKS}
        self.banks["questions.json"] = [self.row]
        self.hints = {"entries": {self.row["id"]: {"singer": {"title": "真實作品"}}}}

    def run_gate(self, baseline_people=()):
        return validate(self.banks, {"schemaVersion": 1, "baselineMainSha": SHA,
                                     "people": list(baseline_people)}, self.root, self.hints)

    def test_new_reviewed_cc_photo_and_sha_pass(self):
        report = self.run_gate()
        self.assertFalse(report["errors"])
        self.assertEqual(report["newOrChangedEntries"], ["t1500_0001"])
        self.assertFalse(report["certifiesPhotoRights"])

    def test_new_rights_missing_human_and_wrong_pixels_fail(self):
        self.row["humanReviewed"] = False
        self.row["attribution"]["license"] = "Copyright retained"
        self.row["gameSha256"] = "b" * 64
        result = self.run_gate()
        self.assertGreaterEqual(len(result["errors"]), 3)

    def test_unchanged_legacy_debt_is_not_certified(self):
        self.row["humanReviewed"] = False
        self.row["attribution"]["license"] = "Copyright retained"
        base = snapshot("questions.json", self.row)
        result = self.run_gate([base])
        self.assertFalse(result["errors"])
        self.assertEqual(result["unchangedLegacyMetadataDebt"], ["t1500_0001"])
        self.row["photo"] = "photos/replacement.jpg"
        self.assertTrue(self.run_gate([base])["errors"])

    def test_missing_baseline_and_cross_bank_duplicate_fail(self):
        base = snapshot("questions.json", self.row)
        self.banks["questions.json"] = []
        self.assertTrue(any("removed" in e for e in self.run_gate([base])["errors"]))
        self.banks["questions.json"] = [self.row]
        self.banks["actors.json"] = [self.row]
        self.assertTrue(any("duplicate" in e for e in self.run_gate()["errors"]))

    def test_bad_license_url_and_reveal_fail(self):
        self.assertTrue(license_ok(self.row["attribution"]))
        self.row["attribution"]["licenseUrl"] = "https://creativecommons.org/licenses/by-sa/99.0/"
        self.assertFalse(license_ok(self.row["attribution"]))
        self.row["reveal"]["eyes"] = [0, 0, 1, 1]
        self.assertFalse(verify_reveal(self.row["reveal"]))


if __name__ == "__main__":
    unittest.main()
