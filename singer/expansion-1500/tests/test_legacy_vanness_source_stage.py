"""Offline guards for exact-source staging; not a human photo approval."""
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.legacy_source_stage import (RELEASE_GATE, commons_original_url, verify_original)


class LegacyVannessSourceStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = json.loads((ROOT / "pipeline/legacy-portrait-request.json").read_text(encoding="utf-8"))
        cls.item = cls.req["items"][0]

    def test_exact_file_and_rights_provenance(self):
        item = self.item
        self.assertEqual(self.req["releaseGate"], RELEASE_GATE)
        self.assertEqual(len(self.req["items"]), 1)
        self.assertEqual(item["person"], "吳建豪")
        self.assertEqual(item["bankId"], "s227")
        self.assertEqual(item["sha1"], "6b9e1b452ebb365f911e8a87039168c02c5765c4")
        self.assertEqual(item["license"], "CC BY-SA 3.0 Unported")
        self.assertEqual(item["author"], "Rico Shen (BrockF5)")
        self.assertEqual(item["dimensions"], [2304, 3072])
        self.assertEqual(item["size"], 2048563)
        self.assertEqual(commons_original_url(item["filename"]),
                         "https://upload.wikimedia.org/wikipedia/commons/a/a8/AdidasRunFor2008OlympicsInTaiwan_Vanness_Wu.jpg")

    def test_geometry_and_masks_expand(self):
        item = self.item
        x0, y0, x1, y1 = item["cropBox"]
        self.assertEqual((x1-x0)*6, (y1-y0)*5)
        self.assertTrue(0 <= x0 < x1 <= 2304 and 0 <= y0 < y1 <= 3072)
        r = item["reveal"]
        self.assertEqual(r["full"], [0,0,1,1])
        for a,b in zip(("eyes","nose","mouth"),("nose","mouth","chin")):
            self.assertLessEqual(r[b][0],r[a][0])
            self.assertLessEqual(r[b][1],r[a][1])
            self.assertGreaterEqual(r[b][2],r[a][2])
            self.assertGreaterEqual(r[b][3],r[a][3])

    def test_original_bytes_must_match_both_checksums_and_dimensions(self):
        buf = io.BytesIO()
        Image.new("RGB",(20,24),"white").save(buf,"JPEG")
        data = buf.getvalue()
        sha1 = hashlib.sha1(data).hexdigest()
        sha256 = hashlib.sha256(data).hexdigest()
        self.assertEqual(verify_original(data,sha1,len(data),[20,24]),sha256)
        with self.assertRaises(ValueError):
            verify_original(data,"0"*40,len(data),[20,24])
        with self.assertRaises(ValueError):
            verify_original(data,sha1,len(data)+1,[20,24])
        with self.assertRaises(ValueError):
            verify_original(data,sha1,len(data),[20,25])

    def test_does_not_touch_live_question_banks(self):
        script = (ROOT / "media_pipeline/legacy_source_stage.py").read_text(encoding="utf-8")
        self.assertIn('"eligibleForLive": False', script)
        self.assertIn('"humanReviewed": False', script)
        self.assertNotIn("singer/photos/",script)
        self.assertNotIn("git push",script)


if __name__ == "__main__":
    unittest.main()
