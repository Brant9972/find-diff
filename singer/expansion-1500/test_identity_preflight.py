import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).with_name("identity_preflight.py")
spec = importlib.util.spec_from_file_location("identity_preflight", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class IdentityPreflightTests(unittest.TestCase):
    def test_short_name_does_not_match_restaurant(self):
        self.assertEqual(mod.collisions({"name": "家家"}, [("actors.json", {"id": "x", "name": "家家美食"})]), [])

    def test_short_name_does_not_match_longer_artist(self):
        self.assertEqual(mod.collisions({"name": "黃玠"}, [("questions.json", {"id": "x", "name": "黃玠瑋"})]), [])

    def test_alias_collision(self):
        found = mod.collisions({"name": "羅璧玲"}, [("variety.json", {"id": "x1000_p0217", "name": "羅霈穎", "aliases": ["羅璧玲", "東區羅姐"]})])
        self.assertEqual(found[0]["id"], "x1000_p0217")

    def test_qid_collision(self):
        found = mod.collisions({"name": "Different spelling", "qid": "Q701907"}, [("actors.json", {"name": "黃智賢", "wikidataQid": "Q701907"})])
        self.assertEqual(len(found), 1)

    def test_release_plan_selected_new_input_shape(self):
        payload = {"selectedNew": [{"plannedQuestionId": "t1500_0181", "name": "王大陸"}]}
        candidates = payload.get("candidates", payload.get("items", payload.get("selectedNew")))
        self.assertEqual(candidates[0]["plannedQuestionId"], "t1500_0181")

    def test_accepted_answer_alias_collision(self):
        found = mod.collisions(
            {"name": "羅璧玲", "acceptedAnswers": ["東區羅姐"]},
            [("variety.json", {"id": "x1000_p0217", "name": "羅霈穎", "aliases": ["東區羅姐"]})],
        )
        self.assertEqual(len(found), 1)

    def test_planned_id_collision(self):
        found = mod.collisions(
            {"plannedQuestionId": "t1500_0181", "name": "Different name"},
            [("actors.json", {"id": "t1500_0181", "name": "王大陸"})],
        )
        self.assertEqual(len(found), 1)

    def test_unicode_normalization(self):
        self.assertEqual(mod.normalize("ＡＢＣ ・ D"), "abcd")


if __name__ == "__main__":
    unittest.main()
