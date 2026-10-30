#!/usr/bin/env python3
"""Offline regression tests for new-person release evidence; no external network."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rights_release_gate import validate


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "singer/expansion-1500").mkdir(parents=True)
        (self.root / "singer/photos").mkdir(parents=True)
        self.photo = self.root / "singer/photos/new.jpg"
        Image.new("RGB", (600, 720), (80, 90, 100)).save(self.photo, format="JPEG")
        self.q = {
            "id": "new001", "name": "新人物", "aliases": ["新人物"],
            "photo": "photos/new.jpg",
            "gameSha256": hashlib.sha256(self.photo.read_bytes()).hexdigest(),
            "humanReviewed": True, "photoStatus": "manually_reviewed_source_and_photo",
            "recognitionContext": "Actual source portrait and five stages reviewed by human, with no obstruction.",
            "wikidataId": "Q123456789",
            "attribution": {
                "source": "https://commons.wikimedia.org/wiki/File:Example.jpg",
                "artist": "Photographer", "credit": "Photographer credited",
                "attribution": "Photographer, cropped from original",
                "license": "CC BY-SA 4.0",
                "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/"
            },
            "reveal": {
                "eyes": [0.08, 0.2, 0.92, 0.35],
                "nose": [0.08, 0.2, 0.92, 0.5],
                "mouth": [0.08, 0.2, 0.92, 0.65],
                "chin": [0.08, 0.2, 0.92, 0.8],
                "full": [0, 0, 1, 1]
            }
        }
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        baseline = {"uniquePeople": 0, "ids": []}
        (self.root / "singer/expansion-1500/rights-release-baseline-20261031.json").write_text(json.dumps(baseline))
        (self.root / "singer/hints.json").write_text(json.dumps({"entries": {"new001": {
            "singer": {"title": "Test Song", "source": "https://example.org/work", "review": "verified"}
        }}}))
        for bank, path in (("singer", "questions"), ("actors", "actors"), ("variety", "variety")):
            (self.root / f"singer/{path}.json").write_text(json.dumps({"questions": [self.q] if bank == "singer" else []}))

    def assert_fail(self, text):
        errors, _ = validate(self.root, strict_baseline=False)
        self.assertTrue(any(text in error for error in errors), errors)

    def test_complete_new_person_passes_metadata_gate(self):
        errors, stats = validate(self.root, strict_baseline=False)
        self.assertEqual(errors, [])
        self.assertEqual(stats["newPeople"], 1)

    def test_missing_open_licence_fails(self):
        self.q["attribution"]["license"] = "Copyright retained by source"
        self.save()
        self.assert_fail("permitted explicit reuse licence")

    def test_licence_url_mismatch_fails(self):
        self.q["attribution"]["licenseUrl"] = "https://creativecommons.org/licenses/by/4.0/"
        self.save()
        self.assert_fail("licence URL does not match")

    def test_bad_photo_hash_fails(self):
        self.q["gameSha256"] = "0" * 64
        self.save()
        self.assert_fail("does not match file")

    def test_wrong_photo_dimensions_fail_even_with_matching_hash(self):
        Image.new("RGB", (599, 720), (80, 90, 100)).save(self.photo, format="JPEG")
        self.q["gameSha256"] = hashlib.sha256(self.photo.read_bytes()).hexdigest()
        self.save()
        self.assert_fail("game photo must be 600x720")

    def test_corrupt_photo_fails_even_with_matching_hash(self):
        self.photo.write_bytes(b"not a decodable image")
        self.q["gameSha256"] = hashlib.sha256(self.photo.read_bytes()).hexdigest()
        self.save()
        self.assert_fail("game photo cannot be decoded")

    def test_no_human_review_fails(self):
        self.q["humanReviewed"] = False
        self.save()
        self.assert_fail("human review metadata")

    def test_bad_reveal_fails(self):
        self.q["reveal"]["eyes"][3] = 0.7
        self.save()
        self.assert_fail("invalid five-stage")

    def test_new_canonical_name_matching_old_alias_is_blocked(self):
        self.q["name"] = "羅璧玲"
        self.q["aliases"] = ["羅璧玲"]
        self.save()
        legacy = {"id": "old001", "name": "羅霈穎",
                  "aliases": ["羅霈穎", "羅璧玲"]}
        (self.root / "singer/actors.json").write_text(json.dumps({"questions": [legacy]}))
        (self.root / "singer/expansion-1500/rights-release-baseline-20261031.json").write_text(
            json.dumps({"uniquePeople": 1, "ids": ["old001"]}))
        self.assert_fail("alias/answer collision")

    def test_new_alias_matching_existing_person_is_blocked(self):
        self.q["aliases"].append("舊藝名")
        self.save()
        legacy = {"id": "old001", "name": "另一位藝人",
                  "aliases": ["另一位藝人", "舊藝名"]}
        (self.root / "singer/actors.json").write_text(json.dumps({"questions": [legacy]}))
        (self.root / "singer/expansion-1500/rights-release-baseline-20261031.json").write_text(
            json.dumps({"uniquePeople": 1, "ids": ["old001"]}))
        self.assert_fail("alias/answer collision")

    def test_existing_legacy_id_is_not_mistaken_for_rights_approval(self):
        baseline = {"uniquePeople": 1, "ids": ["new001"]}
        (self.root / "singer/expansion-1500/rights-release-baseline-20261031.json").write_text(json.dumps(baseline))
        self.q["attribution"]["license"] = "Copyright retained by original source; no open licence asserted"
        for bank, path in (("singer", "questions"), ("actors", "actors"), ("variety", "variety")):
            (self.root / f"singer/{path}.json").write_text(json.dumps({"questions": [self.q] if bank == "singer" else []}))
        errors, stats = validate(self.root, strict_baseline=False)
        self.assertEqual(errors, [])
        self.assertEqual(stats["newPeople"], 0)


if __name__ == "__main__":
    unittest.main()
