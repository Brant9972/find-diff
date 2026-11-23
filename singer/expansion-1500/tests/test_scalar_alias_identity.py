"""Regression: scalar aliases must not become one-character search identities."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import identity


class ScalarAliasIdentityTests(unittest.TestCase):
    def test_scalar_alias_is_full_name(self):
        person = {"name": "葉佳修", "aliases": "Joseph Yeh", "acceptedAnswers": "葉佳修"}
        self.assertEqual(identity(person, "Joseph Yeh, singer"), ["Joseph Yeh"])
        self.assertEqual(identity(person, "A unrelated file"), [])

    def test_alias_list_still_works(self):
        person = {"name": "家家", "aliases": ["Jia Jia"], "acceptedAnswers": []}
        self.assertEqual(identity(person, "香港家家美食餐廳"), [])
        self.assertEqual(identity(person, "Jia Jia on stage"), ["Jia Jia"])

    def test_null_aliases(self):
        person = {"name": "黃玠", "aliases": None, "acceptedAnswers": None}
        self.assertEqual(identity(person, "黃玠瑋 Zooey Wonder"), [])
        self.assertEqual(identity(person, "歌手黃玠演出"), ["黃玠"])


if __name__ == "__main__":
    unittest.main()
