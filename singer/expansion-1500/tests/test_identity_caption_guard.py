import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity_caption_guard import caption_mentions_identity, eligible_for_identity_review


class IdentityCaptionRegression(unittest.TestCase):
    def test_food_business_not_singer(self):
        self.assertFalse(caption_mentions_identity("香港家家美食餐廳招牌", ["家家"]))

    def test_different_artist_not_huang_jie(self):
        self.assertFalse(caption_mentions_identity("黃玠瑋 Zooey Wonder", ["黃玠"]))

    def test_correct_artist_caption(self):
        self.assertTrue(caption_mentions_identity("歌手 家家 於金曲獎紅毯", ["家家"]))
        self.assertTrue(caption_mentions_identity("黃玠 在台北演出", ["黃玠"]))

    def test_qid_conflict(self):
        self.assertFalse(eligible_for_identity_review("歌手 家家", ["家家"], "Q123", "Q456"))

    def test_romanized_word_boundary(self):
        self.assertFalse(caption_mentions_identity("Jason Kingsley", ["Jason King"]))
        self.assertTrue(caption_mentions_identity("Jason King, singer", ["Jason King"]))

    def test_group_caption_not_face_proof(self):
        # A positive name mention is only a lead, NEVER an identity approval.
        self.assertTrue(caption_mentions_identity("林生祥 與友人合照", ["林生祥"]))


if __name__ == "__main__":
    unittest.main()
