"""Reject misleading film-location signs and English 'Chapman to' documents."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import obvious_nonportrait_scene
from media_pipeline.sources import identity


class FilmSignsAndPrepositionTest(unittest.TestCase):
    def test_film_location_signs_are_not_actor_photos(self):
        for filename in (
            'GD Guangdong Foshan National Arts Studio film location signs April 2018 Michael Tse.jpg',
            'GD Guangdong Foshan National Arts Studio film location signs April 2018 Michael Tse 02.jpg',
            '國藝影視城電影海報謝天華.jpg',
            'National Arts Studio signage with celebrity name.jpg',
        ):
            with self.subTest(filename=filename):
                self.assertTrue(obvious_nonportrait_scene({
                    'filename': filename, 'caption': '香港演員謝天華'}))
        self.assertFalse(obvious_nonportrait_scene({
            'filename': 'Michael Tse actor portrait at a movie premiere.jpg',
            'caption': '香港演員謝天華'}))

    def test_chapman_to_is_not_english_preposition_in_archival_letter(self):
        person = {'name': '杜汶澤', 'aliases': ['Chapman To']}
        self.assertEqual(identity(person,
            'Labuan - William Chapman to Fitzgerald - sends list of names.jpg'), [])
        self.assertEqual(identity(person,
            'Chapman To Man-chat attends film premiere'), ['Chapman To'])
        self.assertEqual(identity(person,
            'Hong Kong actor Chapman To interview'), ['Chapman To'])

    def test_exact_sign_sources_stay_excluded_without_banning_performer(self):
        import json
        plan = json.loads((Path(__file__).resolve().parents[1] /
            'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(x for x in plan['selectedNew']
                      if x['plannedQuestionId'] == 't1500_0565')
        self.assertEqual(person['name'], '謝天華')
        signs = [url for url in person['excludedPhotoSources']
                 if 'film_location_signs' in url]
        self.assertEqual(len(signs), 2)
        self.assertNotEqual(person['photoStatus'], 'published')
        self.assertFalse(person['imageVerification']['finalCropReviewed'])


if __name__ == '__main__':
    unittest.main()
