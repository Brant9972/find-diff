"""Guard the exact Huang Shao-ku V2 staged geometry; not a photo approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HuangShaoKuRevealV2Test(unittest.TestCase):
    def test_same_source_and_crop_with_tighter_chin_boundary(self):
        first = json.loads((ROOT / 'pipeline/manual-crop-request-20261031-huangshaoku.json')
                           .read_text(encoding='utf-8'))['items'][0]
        second = json.loads((ROOT / 'pipeline/manual-crop-request-20261031-huangshaoku-v2.json')
                            .read_text(encoding='utf-8'))['items'][0]
        for key in ('personId', 'sourceCandidateId', 'sourceSha256', 'box'):
            self.assertEqual(first[key], second[key])
        self.assertEqual(second['personId'], 't1500_0108')
        self.assertEqual(second['reveal']['eyes'], first['reveal']['eyes'])
        self.assertEqual(second['reveal']['nose'], first['reveal']['nose'])
        self.assertLess(second['reveal']['mouth'][3], first['reveal']['mouth'][3])
        self.assertLess(second['reveal']['chin'][3], first['reveal']['chin'][3])
        self.assertEqual(second['reveal']['full'], [0, 0, 1, 1])


if __name__ == '__main__':
    unittest.main()
