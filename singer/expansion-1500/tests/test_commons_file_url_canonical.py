"""Canonical Commons file URLs must preserve human source rejections."""
import sys
import unittest
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import source_key, excluded_commons_keys


class CommonsFileUrlCanonicalTest(unittest.TestCase):
    def test_path_query_and_language_variants_share_exact_file_key(self):
        filename = "家家 美食誤配 2021.jpg"
        canonical = "https://commons.wikimedia.org/wiki/File:" + quote(filename.replace(" ", "_"))
        variants = [
            canonical,
            "https://commons.wikimedia.org/wiki/File:" + quote(filename),
            "https://commons.wikimedia.org/w/index.php?title=" + quote("File:" + filename.replace(" ", "_")),
            "https://commons.wikimedia.org/w/index.php?title=" + quote("File:" + filename) + "&oldid=12345",
            "https://zh.wikipedia.org/wiki/File:" + quote(filename.replace(" ", "_")),
        ]
        for url in variants:
            with self.subTest(url=url):
                self.assertEqual(source_key(url), source_key(canonical))

    def test_rejected_query_url_blocks_exact_commons_file(self):
        filename = "黃玠瑋 Zooey Wonder 2024.jpg"
        person = {"excludedPhotoSources": [
            "https://commons.wikimedia.org/w/index.php?title=" +
            quote("File:" + filename.replace(" ", "_")) + "&oldid=111"
        ]}
        exact = "https://commons.wikimedia.org/wiki/File:" + quote(filename.replace(" ", "_"))
        self.assertIn(source_key(exact), excluded_commons_keys(person))
        self.assertNotIn(
            source_key("https://commons.wikimedia.org/wiki/File:Other_Portrait.jpg"),
            excluded_commons_keys(person))

    def test_untrusted_host_cannot_impersonate_commons_file_page(self):
        name = "https://commons.wikimedia.org/wiki/File:Portrait.jpg"
        spoof = "https://example.org/wiki/File:Portrait.jpg"
        self.assertNotEqual(source_key(name), source_key(spoof))
        self.assertEqual(excluded_commons_keys({"excludedPhotoSources": [spoof]}), set())

    def test_non_file_index_queries_remain_distinct(self):
        a = "https://commons.wikimedia.org/w/index.php?title=Special:Search&search=actor"
        b = "https://commons.wikimedia.org/w/index.php?title=Special:Search&search=singer"
        self.assertNotEqual(source_key(a), source_key(b))


if __name__ == "__main__":
    unittest.main()
