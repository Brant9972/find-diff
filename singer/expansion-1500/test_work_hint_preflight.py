"""Regression tests for expansion candidate work-hint preflight."""
import importlib.util
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).with_name("work_hint_preflight.py")
spec = importlib.util.spec_from_file_location("work_hint_preflight", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class WorkHintPreflightTests(unittest.TestCase):
    def test_known_invalid_award(self):
        data = {"selectedNew": [{"candidateId": "t1500_0276", "name": "許書豪",
                                 "representativeWorks": ["金曲獎"]}]}
        self.assertEqual(len(module.scan(data)), 1)

    def test_actual_works_pass(self):
        data = {"selectedNew": [{"candidateId": "t1500_0355", "name": "黃智賢",
                                 "representativeWorks": ["潛行狙擊"]}]}
        self.assertEqual(module.scan(data), [])

    def test_award_with_book_title_punctuation(self):
        self.assertEqual(len(module.scan({"candidateId": "x", "representativeWorks": ["《金鐘獎》"]})), 1)

    def test_no_false_positive_on_other_fields(self):
        self.assertEqual(module.scan({"candidateId": "x", "name": "金曲獎",
                                      "representativeWorks": ["某歌曲"]}), [])

if __name__ == "__main__":
    unittest.main()
