"""Regression checks for exact Chinese stage-name boundaries."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "media_pipeline" / "sources.py"
spec = importlib.util.spec_from_file_location("media_pipeline_sources_boundary", MODULE)
sources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sources)


class IdentityBoundaryTests(unittest.TestCase):
    def test_short_stage_name_does_not_match_embedded_text(self):
        person = {"name": "家家", "aliases": []}
        for caption in ("家家美食", "家家food", "家家2026", "家家_2026", "我家家家"):
            with self.subTest(caption=caption):
                self.assertFalse(sources.identity(person, caption))

    def test_long_name_does_not_match_embedded_text(self):
        person = {"name": "金城武", "aliases": []}
        for caption in ("金城武樹", "金城武2026", "金城武_photo", "abc金城武"):
            with self.subTest(caption=caption):
                self.assertFalse(sources.identity(person, caption))

    def test_contextual_captions_still_match(self):
        self.assertTrue(sources.identity({"name": "家家", "aliases": []}, "歌手家家演出"))
        self.assertTrue(sources.identity({"name": "金城武", "aliases": []}, "金城武出席"))
        self.assertTrue(sources.identity({"name": "金城武", "aliases": []}, "金城武"))

if __name__ == "__main__":
    unittest.main()
