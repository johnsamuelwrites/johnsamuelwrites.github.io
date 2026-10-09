import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'main'))
from abstract.reconcile_translation_content import changed_values, plan


class TranslationContentTests(unittest.TestCase):
    def entity(self):
        return {'labels': {'fr': {'value': 'Vienne'}}, 'claims': {
            'P8': [{'mainsnak': {'datavalue': {'value': {'id': 'Q3185'}}}}],
            'P40': [{'id': 'Q1$statement', 'rank': 'preferred',
                     'qualifiers': {'P42': [{'snaktype': 'value'}]},
                     'references': [{'hash': 'reference'}],
                     'mainsnak': {'datavalue': {'value': {'language': 'fr', 'text': 'Vienna'}}}}]}}

    def test_preserves_statement_metadata_and_input(self):
        entity = self.entity()
        original = copy.deepcopy(entity)
        edits, blocked = plan(entity, {'fr': 'Vienne'})
        self.assertEqual(blocked, [])
        expected = copy.deepcopy(entity['claims']['P40'][0])
        expected['mainsnak']['datavalue']['value']['text'] = 'Vienne'
        self.assertEqual(edits, [expected])
        self.assertEqual(entity, original)

    def test_changed_live_label_blocks_write(self):
        self.assertEqual(plan(self.entity(), {'fr': 'Paris'})[0], [])
        self.assertTrue(plan(self.entity(), {'fr': 'Paris'})[1])

    def test_composition_and_duplicate_claims_block_write(self):
        entity = self.entity()
        entity['claims']['P8'].append({'mainsnak': {'datavalue': {'value': {'id': 'Q3835'}}}})
        self.assertEqual(plan(entity, {'fr': 'Vienne'})[0], [])
        self.assertTrue(plan(entity, {'fr': 'Vienne'})[1])
        entity = self.entity()
        entity['claims']['P40'] *= 2
        self.assertTrue(plan(entity, {'fr': 'Vienne'})[1])

    def test_repeat_is_noop(self):
        entity = self.entity()
        entity['claims']['P40'] = plan(entity, {'fr': 'Vienne'})[0]
        self.assertEqual(plan(entity, {'fr': 'Vienne'}), ([], []))

    def test_diff_ignores_unchanged_and_empty_values(self):
        before = 'identifier,itemtype,en,fr\nQ1,Q3185,Vienna,Vienna\n'
        after = 'identifier,itemtype,en,fr\nQ1,Q3185,Vienna,Vienne\nQ2,Q3185,Paris,\n'
        self.assertEqual(changed_values(before, after), {'Q1': {'fr': 'Vienne'}, 'Q2': {'en': 'Paris'}})
