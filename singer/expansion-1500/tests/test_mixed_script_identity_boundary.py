"""Regression: mixed-script substrings must not identify a celebrity photo."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from media_pipeline.sources import identity


class MixedScriptIdentity(unittest.TestCase):
    def test_short_cjk_names_embedded_in_identifiers(self):
        for name, caption in [
            ("家家", "家家food"), ("家家", "abc家家"),
            ("黃玠", "黃玠2026"), ("黃玠", "黃玠瑋 Zooey Wonder"),
            ("金城武", "abc金城武"), ("金城武", "金城武2026"),
        ]:
            with self.subTest(name=name, caption=caption):
                self.assertFalse(identity({"name": name}, caption))

    def test_legitimate_context_remains(self):
        for name, caption in [
            ("家家", "歌手家家在演唱會"), ("黃玠", "黃玠 在台北演出"),
            ("金城武", "演員金城武出席記者會"),
        ]:
            with self.subTest(name=name):
                self.assertTrue(identity({"name": name}, caption))


if __name__ == "__main__":
    unittest.main()
