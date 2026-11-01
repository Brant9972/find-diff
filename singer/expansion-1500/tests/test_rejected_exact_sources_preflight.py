"""Cross-check all curated Commons exact leads against earlier human rejections.

This guard is evidence-only. It never removes a person, changes the live
questions or treats a Commons metadata match as visual approval.
"""
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import excluded_commons_keys, source_key


class RejectedExactSourcesPreflightTest(unittest.TestCase):
    def test_all_previously_rejected_curated_sources_are_excluded(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        review = json.loads((ROOT.parent / 'photo-review.json').read_text(encoding='utf-8'))
        rejected = {source_key(item['source']): item for item in review['rejected']
                    if item.get('source')}
        self.assertTrue(rejected)
        for person in plan['selectedNew']:
            exact = [
                'https://commons.wikimedia.org/wiki/File:' + quote(filename.replace(' ', '_'))
                for filename in person.get('reviewExactCommonsFiles', [])
            ]
            exact.extend(item.get('source', '') for item in
                         person.get('reviewVerifiedOriginalSources', []))
            excluded = excluded_commons_keys(person)
            for source in exact:
                key = source_key(source)
                if key in rejected:
                    with self.subTest(person=person['name'], source=source):
                        self.assertIn(key, excluded,
                                      'A human-rejected exact source must be explicitly excluded')


if __name__ == '__main__':
    unittest.main()
