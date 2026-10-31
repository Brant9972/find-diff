"""Cross-bank preflight deduplication: no photo search for already-live people."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_media import reconcile_live_people, select_people


class LiveIdentityPreflightTest(unittest.TestCase):
    def check(self, candidate, live, status='no_suitable_source', pid='t1500_0259'):
        state = {'people': {pid: {
            'personId': pid, 'name': candidate['name'], 'status': status,
            'attempts': 0, 'nextRetryAt': None, 'candidates': [],
        }}}
        reconcile_live_people(state, {pid: candidate}, live)
        return state['people'][pid]

    def test_luo_biling_is_alias_of_existing_luo_peiying(self):
        live = {'x1000_p0217': {'name': '羅霈穎',
                               'aliases': ['羅霈穎', '羅璧玲', '東區羅姐']}}
        row = self.check({'name': '羅璧玲', 'acceptedAnswers': ['羅璧玲']}, live)
        self.assertEqual(row['status'], 'duplicate_existing')
        self.assertEqual(row['duplicateExistingCanonicalId'], 'x1000_p0217')
        self.assertEqual(row['duplicateMatchReason'], 'canonical_matches_live_alias')
        self.assertEqual(select_people({'people': {'t1500_0259': row}},
                                       {'t1500_0259': {'priority': 'A'}},
                                       None, 10, retry_failed=True), [])

    def test_same_name_different_question_id_is_duplicate_not_published(self):
        row = self.check({'name': '張三'}, {'a001': {'name': '張三', 'aliases': []}})
        self.assertEqual(row['status'], 'duplicate_existing')
        self.assertEqual(row['duplicateMatchReason'], 'canonical_name')

    def test_same_qid_across_distinct_names_is_duplicate(self):
        row = self.check({'name': '藝名甲', 'wikidataId': 'Q12345'},
                         {'s001': {'name': '本名乙', 'wikidataId': 'Q12345', 'aliases': []}})
        self.assertEqual(row['status'], 'duplicate_existing')
        self.assertEqual(row['duplicateMatchReason'], 'wikidata_qid')

    def test_candidate_alias_matching_live_canonical(self):
        row = self.check({'name': '藝名甲', 'acceptedAnswers': ['陳信宏']},
                         {'s001': {'name': '陳信宏', 'aliases': ['阿信']}})
        self.assertEqual(row['status'], 'duplicate_existing')
        self.assertEqual(row['duplicateMatchReason'], 'candidate_alias_matches_live_canonical')

    def test_conflicting_curated_qids_are_not_automatically_merged(self):
        row = self.check({'name': '黃智賢', 'wikidataId': 'Q701907'},
                         {'a001': {'name': '黃智賢', 'wikidataId': 'Q9999', 'aliases': []}})
        self.assertEqual(row['status'], 'no_suitable_source')
        self.assertNotIn('duplicateExistingCanonicalId', row)

    def test_generic_two_character_nickname_does_not_cause_false_duplicate(self):
        row = self.check({'name': '小胖', 'acceptedAnswers': ['小胖']},
                         {'a001': {'name': '王先生', 'aliases': ['小胖']}})
        self.assertEqual(row['status'], 'no_suitable_source')

    def test_ambiguous_alias_does_not_automatically_merge(self):
        row = self.check({'name': '小百靈'},
                         {'a001': {'name': '歌手甲', 'aliases': ['小百靈']},
                          'a002': {'name': '歌手乙', 'aliases': ['小百靈']}})
        self.assertEqual(row['status'], 'no_suitable_source')

    def test_alias_to_alias_without_canonical_link_is_not_sufficient(self):
        row = self.check({'name': '甲藝名', 'acceptedAnswers': ['共同藝名']},
                         {'a001': {'name': '乙藝名', 'aliases': ['共同藝名']}})
        self.assertEqual(row['status'], 'no_suitable_source')

    def test_exact_live_id_is_published_and_not_researched_again(self):
        row = self.check({'name': '某歌手'},
                         {'t1500_0259': {'name': '某歌手', 'aliases': []}})
        self.assertEqual(row['status'], 'published')

    def test_stale_published_status_not_accepted_as_live_evidence(self):
        row = self.check({'name': '另一人'}, {'s001': {'name': '不相關', 'aliases': []}},
                         status='published')
        self.assertEqual(row['status'], 'no_suitable_source')
        self.assertIn('absent_from_current_live', row['preflightWarning'])

    def test_cross_bank_duplicate_question_ids_share_one_identity(self):
        row = self.check({'name': '羅璧玲'},
                         {'a001': {'name': '羅霈穎', 'aliases': ['羅璧玲']},
                          'v001': {'name': '羅霈穎', 'aliases': ['羅璧玲']}})
        self.assertEqual(row['status'], 'duplicate_existing')
        self.assertIn(row['duplicateExistingCanonicalId'], {'a001', 'v001'})


if __name__ == '__main__':
    unittest.main()
