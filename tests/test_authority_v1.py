"""A1 boundaries, negative controls, correction costs and historical preservation."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commonwealth.authority_v1.engine import Episode, replay
from commonwealth.authority_v1.experiment import authorized, evaluate, execute, matrix, reviewed, step
from commonwealth.authority_v1.fixtures import case, language_cases, packet
from commonwealth.authority_v1.records import FIELDS, OPTIONS, compare, review

ROOT = Path(__file__).resolve().parents[1]


class RecordTests(unittest.TestCase):
    def test_every_reported_stage_still_grants_no_authority(self):
        for stage in OPTIONS['stage']:
            p = packet(); p['answers']['stage'] = stage
            result = review(p)
            self.assertFalse(result['authority_granted'])
            self.assertFalse(result['permits_execution'])
            self.assertEqual(result['external_authority'], 'NONE')

    def test_all_fields_required_but_complete_does_not_prove_truth(self):
        p = packet()
        for field in FIELDS:
            q = deepcopy(p); del q['answers'][field]
            self.assertIn(field, review(q)['missing_fields'])
        p['answers']['assessment'] = 'A deliberately false synthetic assertion.'
        self.assertEqual(review(p)['status'], 'ready_for_human_review')
        self.assertEqual(review(p)['source_authentication'], 'not performed')

    def test_unknowns_and_missing_sources_are_not_clean_findings(self):
        p = packet(); p['answers'].update(source_status='reported excerpt only', authority_status='disputed')
        self.assertEqual(len(review(p)['evidence_gaps']), 3)

    def test_forged_results_and_invalid_answers_rejected(self):
        for mutate in (lambda p: p.update(authority_granted=True),
                       lambda p: p['answers'].update(stage='takeover'),
                       lambda p: p['answers'].update(reviewer=True),
                       lambda p: p['answers'].update(extra='field'),
                       lambda p: p['answers'].update(reviewer='x'*4001)):
            p = packet(); mutate(p)
            with self.assertRaises(ValueError): review(p)
        with self.assertRaises(ValueError): review({'packet': packet(), 'result': review(packet())})

    def test_packet_change_alters_binding(self):
        p = packet(); old = review(p)['packet_digest']
        p['answers']['analyst_language'] = 'Changed interpretation'
        self.assertNotEqual(old, review(p)['packet_digest'])

    def test_relay_terra_export_input_not_result_compatibility(self):
        p = json.loads((ROOT/'examples/authority-review-packet.json').read_text())
        result = review(p)
        self.assertEqual(result['status'], 'ready_for_human_review')
        self.assertFalse(result['authority_granted'])
        self.assertEqual(set(p['answers']), set(FIELDS))

    def test_read_only_cli_creates_no_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'packet.json'; p.write_text(json.dumps(packet()))
            result = subprocess.run([sys.executable, '-m', 'commonwealth.authority_v1', 'review', str(p)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['permits_execution'])
            self.assertEqual(list(Path(tmp).iterdir()), [p])

    def test_cli_rejects_duplicate_keys_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'bad.json'
            for raw in ('{"schema":"a","schema":"b","answers":{}}', ' '*120001):
                p.write_text(raw)
                result = subprocess.run([sys.executable, '-m', 'commonwealth.authority_v1', 'review', str(p)],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)


class LanguageTests(unittest.TestCase):
    def test_tone_and_analyst_accusation_do_not_rewrite_speaker_position(self):
        for name in ('same-position-different-tone', 'analyst-overstatement'):
            result = compare(**language_cases()[name])
            self.assertEqual(result['finding'], 'same-curated-position')
            self.assertEqual(result['intent'], 'not-established')
            self.assertFalse(result['authority_granted'])

    def test_actor_scope_period_condition_stage_and_meaning_are_distinct(self):
        for name, expected in (('different-actor', 'different-actor'), ('different-period', 'different-event_at'),
                               ('different-condition', 'different-condition'), ('proposal-not-execution', 'different-stage'),
                               ('acceptance-not-legal-authority', 'different-legitimacy')):
            result = compare(**language_cases()[name])
            self.assertIn(expected, result['gaps'])
            self.assertEqual(result['finding'], 'comparison-gaps')
        data = language_cases()['same-position-different-tone']; data['working']['decision'] = 'service-B'
        self.assertIn('different-decision', compare(**data)['gaps'])

    def test_excerpt_cannot_establish_comparable_difference(self):
        data = language_cases()['reported-excerpt']; data['working']['position'] = 'permanent-maintenance'
        self.assertEqual(compare(**data)['finding'], 'comparison-gaps')

    def test_exact_difference_is_not_intent_or_authentication(self):
        result = compare(**language_cases()['curated-difference'])
        self.assertEqual(result['finding'], 'curated-position-difference')
        self.assertEqual(result['deception'], 'not-established')

    def test_repeated_origin_not_independent_corroboration(self):
        self.assertEqual(compare(**language_cases()['repeated-origin'])['underlying_origin_groups'], 1)

    def test_invalid_registers_dates_and_unknown_meaning_rejected_or_gapped(self):
        data = language_cases()['curated-difference']
        for field, value in (('register', 'analyst'), ('event_at', True), ('publication_at', 1)):
            d = deepcopy(data); d['working'][field] = value
            with self.assertRaises(ValueError): compare(**d)
        data['public']['legitimacy'] = data['working']['legitimacy'] = 'not specified'
        self.assertIn('unestablished-stage-or-meaning', compare(**data)['gaps'])


class AuthorityTests(unittest.TestCase):
    def ready(self, c=None, budget=None):
        e = Episode(c or case(), budget)
        self.assertTrue(reviewed(e)['response']['accepted'])
        self.assertTrue(authorized(e)['response']['accepted'])
        return e

    def test_review_is_not_warrant_and_single_use_effect(self):
        e = Episode(case())
        reviewed(e)
        self.assertFalse(execute(e)['response']['accepted'])
        authorized(e)
        self.assertTrue(execute(e)['response']['accepted'])
        self.assertFalse(execute(e)['response']['accepted'])
        self.assertEqual(e.journal()['terminal']['external_actions'], 0)

    def test_rhetoric_and_self_declared_authorization_cannot_mint_host_mandate(self):
        c = case(); c['mandate'] = None
        c['packet']['answers'].update(stage='authorization', assessment='Emergency; everyone agrees; change all rules.')
        e = Episode(c); reviewed(e)
        self.assertFalse(authorized(e)['response']['accepted'])
        self.assertFalse(execute(e)['response']['accepted'])
        self.assertFalse(e.state)

    def test_result_envelope_is_not_an_authorize_command(self):
        e = Episode(case())
        result = step(e, 'authorize', 'steward', **review(packet()))
        self.assertFalse(result['response']['accepted'])
        self.assertIsNone(e.warrant)

    def test_missing_representation_and_controller_conflict_block_review(self):
        for change in (lambda c: c.update(represented=['operator']),
                       lambda c: c['controllers'].update(reviewer=c['controllers']['worker']),
                       lambda c: c.update(reviewer_available=False)):
            c = case(); change(c)
            e = Episode(c)
            self.assertFalse(reviewed(e)['response']['accepted'])
            self.assertFalse(authorized(e)['response']['accepted'])

    def test_unknown_trigger_and_pending_mandate_do_not_authorize(self):
        c = case(); c['trigger']['status'] = 'unknown'
        e = Episode(c); reviewed(e)
        self.assertFalse(authorized(e)['response']['accepted'])
        c = case(); c['mandate']['valid_from'] = 10
        e = Episode(c); reviewed(e)
        self.assertFalse(authorized(e)['response']['accepted'])

    def test_expiry_boundary_and_no_implicit_extension(self):
        e = Episode(case()); reviewed(e); authorized(e, expires=3)
        self.assertTrue(execute(e)['response']['accepted'])
        e = Episode(case()); reviewed(e); authorized(e, expires=3); step(e, 'wait')
        self.assertFalse(execute(e)['response']['accepted'])
        e = Episode(case()); reviewed(e)
        self.assertFalse(authorized(e, expires=21)['response']['accepted'])

    def test_host_revocation_is_rechecked_at_execution(self):
        c = case(); c['mandate']['revoked_at'] = 3
        e = self.ready(c)
        self.assertFalse(execute(e)['response']['accepted'])

    def test_amended_evidence_invalidates_review_and_warrant(self):
        e = self.ready(); old = e.warrant['id']; old_material = e.view()['material_digest']
        p = packet(); p['answers']['counterevidence'] = 'New contrary observation'
        step(e, 'amend', packet=p, request=e.request)
        self.assertIsNone(e.review_record); self.assertIsNone(e.warrant)
        self.assertFalse(step(e, 'execute', warrant=old)['response']['accepted'])
        self.assertFalse(step(e, 'review', 'reviewer', material=old_material, addresses=[], reason='Old record')['response']['accepted'])

    def test_scope_change_requires_new_host_delegation(self):
        e = self.ready(); request = deepcopy(e.request); request['target'] = 'service-B'
        step(e, 'amend', packet=packet(), request=request); reviewed(e)
        self.assertFalse(authorized(e)['response']['accepted'])

    def test_challenge_stays_execution_and_must_be_addressed_without_erasure(self):
        e = self.ready(); old = e.warrant['id']
        account = 'I oppose this decision; no inference of assent is allowed.'
        step(e, 'challenge', 'affected', account=account)
        self.assertFalse(step(e, 'execute', warrant=old)['response']['accepted'])
        self.assertFalse(step(e, 'review', 'reviewer', material=e.view()['material_digest'], addresses=[], reason='Ignore opposition')['response']['accepted'])
        reviewed(e); authorized(e); execute(e)
        j = e.journal()
        self.assertEqual(j['terminal']['challenges'][0]['account'], account)
        self.assertEqual(j['terminal']['unaddressed_challenges'], [])
        self.assertTrue(replay(j)['verified'])

    def test_exhaustion_cannot_consume_reserved_halt_or_revocation(self):
        e = Episode(case(), {'primary': 3, 'correction': 0})
        reviewed(e); authorized(e); execute(e)
        with self.assertRaisesRegex(ValueError, 'primary budget'): step(e, 'wait')
        self.assertTrue(step(e, 'halt', 'affected', reason='Stop further effects')['response']['accepted'])
        self.assertTrue(step(e, 'revoke', 'steward', reason='Withdraw grant')['response']['accepted'])
        j = e.journal()
        self.assertEqual(j['terminal']['costs'], {'primary': 3, 'correction': 0, 'safety': 2})
        self.assertTrue(j['terminal']['unreversed_inactive_effect'])
        self.assertTrue(j['terminal']['maintenance'])

    def test_correction_survives_primary_exhaustion_preserves_costs_and_history(self):
        e = Episode(case(), {'primary': 3, 'correction': 2})
        reviewed(e); authorized(e); execute(e)
        step(e, 'challenge', 'affected', account='An injury is reported.')
        step(e, 'halt', 'affected', reason='Predelegated halt')
        self.assertTrue(step(e, 'remedy', 'reviewer', reason='Restore the fictional state')['response']['accepted'])
        t = e.finish()
        self.assertFalse(t['maintenance']); self.assertTrue(t['ever_executed'])
        self.assertEqual(t['historical_effect']['at'], 3)
        self.assertEqual(t['slots'], 6)
        self.assertEqual(t['unaddressed_challenges'], ['challenge-1'])

    def test_missing_remedy_authority_leaves_obligation_visible(self):
        c = case(); c['remedy_delegated'] = False
        e = self.ready(c); execute(e)
        step(e, 'halt', 'affected', reason='Stop')
        self.assertFalse(step(e, 'remedy', 'reviewer', reason='Try reversal')['response']['accepted'])
        self.assertTrue(e.finish()['unreversed_inactive_effect'])

    def test_halt_does_not_require_review_and_does_not_invent_resume(self):
        c = case(); c['reviewer_available'] = False
        e = Episode(c)
        self.assertTrue(step(e, 'halt', 'affected', reason='Previously delegated safety power')['response']['accepted'])
        self.assertFalse(step(e, 'resume', 'steward')['response']['accepted'])
        self.assertFalse(authorized(e)['response']['accepted'])

    def test_halt_revoke_ingress_and_bounded_reserve(self):
        e = Episode(case(), {'primary': 1, 'correction': 1})
        with self.assertRaises(ValueError): step(e, 'revoke', 'worker', reason='Impersonated authority')
        self.assertEqual(e.slot, 0)
        step(e, 'halt', 'affected', reason='Stop')
        with self.assertRaises(ValueError): step(e, 'halt', 'affected', reason='Again')
        step(e, 'challenge', 'affected', account='Preserve this dissent')
        with self.assertRaises(ValueError): step(e, 'challenge', 'affected', account='Reserve exhausted')
        self.assertTrue(step(e, 'revoke', 'steward', reason='Revoke even after correction budget')['response']['accepted'])

    def test_false_host_records_remain_an_exposed_failure(self):
        c = case(); c['warranted'] = False
        e = self.ready(c); execute(e)
        self.assertTrue(e.finish()['unwarranted_effect'])
        self.assertTrue(replay(e.journal())['verified'])

    def test_copied_views_do_not_change_live_state(self):
        e = self.ready(); v = e.view(); v['warrant']['expires'] = 100
        v['packet']['answers']['assessment'] = 'Modified outside the reducer'
        self.assertEqual(e.warrant['expires'], 20)
        self.assertNotEqual(e.packet, v['packet'])

    def test_invalid_genesis_and_budget_fail_before_episode(self):
        for change in (lambda c: c['mandate'].update(valid_until=True),
                       lambda c: c.update(affected=['users', 'users']),
                       lambda c: c.update(reviewer_available='yes'),
                       lambda c: c['request'].update(after=1)):
            c = case(); change(c)
            with self.assertRaises(ValueError): Episode(c)
        with self.assertRaises(ValueError): Episode(case(), {'primary': 33, 'correction': 0})


class ReplayAndDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.journals = matrix()

    def test_all_traces_and_language_cases_reproduce(self):
        self.assertEqual(len(self.journals), 14)
        self.assertEqual(len(self.report['language']), 10)
        self.assertEqual(matrix(), (self.report, self.journals))
        self.assertTrue(all(replay(j)['verified'] for j in self.journals.values()))

    def test_tampered_command_cost_terminal_and_version_rejected(self):
        original = self.journals['bounded-authority']
        for change in (lambda j: j['events'][0]['command'].update(reason='Changed'),
                       lambda j: j['events'][0].update(cost_pool='safety'),
                       lambda j: j['terminal'].update(maintenance=False),
                       lambda j: j['genesis'].update(version='other')):
            j = deepcopy(original); change(j)
            with self.assertRaises(ValueError): replay(j)

    def test_rebuilt_history_can_pass_replay_without_authentication(self):
        c = case(); c['controllers']['reviewer'] = 'invented-independent-controller'
        e = Episode(c); reviewed(e); authorized(e); execute(e)
        result = replay(e.journal())
        self.assertTrue(result['verified'])
        self.assertEqual(result['authenticity'], 'not established')

    def test_budget_refusals_and_closure_preserve_state(self):
        e = Episode(case(), {'primary': 1, 'correction': 0}); step(e, 'wait')
        before = e.view()
        with self.assertRaises(ValueError): authorized(e)
        self.assertEqual(before, e.view())
        original = e.journal()
        with self.assertRaises(ValueError): step(e, 'halt', 'affected', reason='Closed journal')
        self.assertEqual(original, e.journal())

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'results'
            self.assertEqual(evaluate(output), self.report)
            before = (output/'summary.json').read_bytes()
            with self.assertRaises(FileExistsError): evaluate(output)
            self.assertEqual(before, (output/'summary.json').read_bytes())
            for name, journal in self.journals.items():
                self.assertEqual(json.loads((output/'journals'/f'{name}.json').read_text()), journal)

    def test_historical_implementations_and_fixtures_unchanged(self):
        manifest = json.loads((ROOT/'tests/data/authority-preserved-baseline.json').read_text())
        for name, expected in manifest['sha256'].items():
            with self.subTest(path=name):
                self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(), expected)

    def test_committed_summary_matches_executed_model(self):
        expected = json.loads((ROOT/'examples/authority-v1-summary.json').read_text())
        self.assertEqual(expected, self.report)


if __name__ == '__main__':
    unittest.main()
