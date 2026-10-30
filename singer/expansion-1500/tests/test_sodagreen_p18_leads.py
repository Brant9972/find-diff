"""Prevent exact P18 discovery leads from being mistaken for live photo approvals."""
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPANSION = ROOT / "expansion-1500"
EXPECTED = {"t1500_0112": ("謝馨儀", "Q15905462", "31"),
            "t1500_0114": ("龔鈺祺", "Q15931223", "24")}


class SodagreenP18LeadsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((EXPANSION / "release-plan-20261028.json").read_text(encoding="utf-8"))
        cls.leads = json.loads((EXPANSION / "pipeline/p18-sodagreen-leads-20261031.json").read_text(encoding="utf-8"))

    def test_only_preselected_non_live_people_are_pinned(self):
        selected = {p["plannedQuestionId"]: p for p in self.plan["selectedNew"]}
        live = []
        for bank in ("questions.json", "actors.json", "variety.json"):
            live.extend(json.loads((ROOT / bank).read_text(encoding="utf-8"))["questions"])
        live_ids = {q["id"] for q in live}
        live_names = {q["name"] for q in live}
        self.assertEqual(len(self.leads["people"]), len(EXPECTED))
        for lead in self.leads["people"]:
            pid = lead["personId"]
            self.assertIn(pid, EXPECTED)
            name, qid, photo_num = EXPECTED[pid]
            person = selected[pid]
            self.assertEqual((lead["name"], lead["wikidataQid"]), (name, qid))
            self.assertEqual(person["wikidataId"], qid)
            self.assertEqual(person["reviewExactCommonsFiles"], [lead["filename"]])
            self.assertIn(f" - {photo_num} (cropped).jpg", lead["filename"])
            self.assertNotIn(pid, live_ids)
            self.assertNotIn(name, live_names)

    def test_discovery_metadata_is_never_release_approval(self):
        self.assertEqual(self.leads["releaseGate"], "NOT_APPROVED_NOT_PLAYABLE")
        for lead in self.leads["people"]:
            self.assertFalse(lead["approvedForLive"])
            self.assertFalse(lead["sourceImageDownloaded"])
            self.assertFalse(lead["gameCropReviewed"])
            self.assertFalse(lead["fiveStageReviewed"])
            self.assertIsNone(lead["gameSha256"])
            self.assertEqual(lead["sourceLicense"], "CC BY-SA 2.0")
            self.assertEqual(lead["licenseUrl"], "https://creativecommons.org/licenses/by-sa/2.0/")
            self.assertTrue(lead["sourcePage"].startswith("https://commons.wikimedia.org/wiki/File:"))
            self.assertIn("Wikidata", " ".join(lead["identityEvidence"]))


if __name__ == "__main__":
    unittest.main()
