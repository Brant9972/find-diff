"""Explicitly requested retained pixels must remain reviewable during cooldown."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_media import retained_source_targets


class RetainedSourceTargetTest(unittest.TestCase):
    def test_explicit_cooldown_target_is_not_dropped(self):
        self.assertEqual(retained_source_targets([], ['t1500_0108']),
                         ['t1500_0108'])

    def test_only_scanned_and_explicit_ids_are_included(self):
        self.assertEqual(retained_source_targets(['t1500_0112'], ['t1500_0108', 't1500_0112']),
                         ['t1500_0108', 't1500_0112'])
        self.assertEqual(retained_source_targets([], []), [])


if __name__ == '__main__':
    unittest.main()
