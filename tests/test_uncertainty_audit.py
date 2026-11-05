"""Counterexamples to the independent checker's stated accounting contract."""
from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

try:
    from .uncertainty_audit_support import trace, rehash
except ImportError:
    from uncertainty_audit_support import trace, rehash

ROOT=Path(__file__).resolve().parents[1]
CHECKER=ROOT/'scripts/audit_uncertainty.mjs'


@unittest.skipUnless(shutil.which('node'),'Node required for independent checker contract')
class AuditContract(unittest.TestCase):
    def run_raw(self,raw,summary=None):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'rows.jsonl';path.write_bytes(raw)
            target='--partial'
            if summary is not None:
                sp=Path(tmp)/'summary.json';sp.write_bytes(summary);target=str(sp)
            return subprocess.run(['node',str(CHECKER),str(path),target],capture_output=True,text=True)

    def run_rows(self,rows,summary=None):
        return self.run_raw((''.join(json.dumps(r)+'\n' for r in rows)).encode(),summary)

    def rejected(self,row,reason):
        rehash(row) # Refusal must survive repaired hashes, not depend on a stale checksum.
        run=self.run_rows([row]);self.assertNotEqual(run.returncode,0);self.assertIn(reason,run.stderr)

    def test_hand_built_first_final_and_historical_partitions(self):
        rows=[trace(first,truth,review) for first,truth,review in product((None,'M','Y'),('M','Y'),('accurate','delayed','wrong','unavailable'))]
        run=self.run_rows(rows);self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['episodes'],24)
        a=trace(None,'M','accurate')['measures']
        self.assertEqual([a[k] for k in ('first_correct','first_wrong','first_absent','final_correct','recoveries_after_abstention','repaired_errors')],[0,0,1,1,1,0])
        b=trace('M','M','wrong')['measures']
        self.assertEqual([b[k] for k in ('first_correct','final_wrong','review_regressions','unresolved_errors','primary_on_time')],[1,1,1,1,True])
        c=trace('Y','M','delayed')['measures']
        self.assertEqual((c['repair_latency_slots'],c['primary_historical_misses']),(14,1))
        d=trace(None,'M','unavailable')['measures']
        self.assertEqual((d['final_absent'],d['never_correct'],d['censored_late_slots']),(1,1,14))

    def test_late_output_cannot_be_relabelled_as_initial(self):
        r=trace(None)
        phase=next(e for e in r['events'] if e['kind']=='abstention')
        phase.update(kind='execution',choice='M')
        r['measures'].update(first_absent=0,first_correct=1,matched_execution_waits=0,recoveries_after_abstention=0,recovery_latency_slots=0)
        self.rejected(r,'command/outer phase linkage')

    def test_first_execution_cannot_be_hidden_with_an_abstention_label(self):
        r=trace();r['events'][1].update(kind='abstention',choice=None)
        self.rejected(r,'command/outer phase linkage')

    def test_unknown_or_malformed_cells_cannot_inflate_coverage(self):
        edits=[lambda r:r.update(policy='invented'),lambda r:r.update(facet='invented'),
               lambda r:r['cell'].update(pattern='invented'),lambda r:r['cell'].update(swapped=1),
               lambda r:r['cell'].update(peer_work=True),lambda r:r['cell'].update(review='invented')]
        for edit in edits:
            with self.subTest(edit=edits.index(edit)):
                r=trace();edit(r);self.rejected(r,'domain')
        r=trace();run=self.run_rows([r,r]);self.assertNotEqual(run.returncode,0);self.assertIn('duplicate cell',run.stderr)
        summary=json.loads((ROOT/'examples/uncertainty-v1-results.json').read_text())
        raw=(json.dumps(r)+'\n').encode();summary.update(episode_count=1,episodes_sha256=sha256(raw).hexdigest())
        run=self.run_raw(raw,json.dumps(summary).encode());self.assertNotEqual(run.returncode,0);self.assertIn('matrix count/digest',run.stderr)

    def test_counter_coercions_are_rejected(self):
        for key,value in [('first_correct','1'),('first_wrong',None),('first_correct',True),('primary_on_time',1)]:
            with self.subTest(key=key,value=value):
                r=trace();r['measures'][key]=value;self.rejected(r,'metric type')

    def test_duplicate_and_escaped_duplicate_names_are_rejected(self):
        raw=json.dumps(trace())
        for pair in ('"policy":"ignored","policy":"constant-M"','"pol\\u0069cy":"ignored","policy":"constant-M"'):
            run=self.run_raw((raw.replace('"policy": "constant-M"',pair)+'\n').encode())
            self.assertNotEqual(run.returncode,0);self.assertIn('duplicate JSON name',run.stderr)
        summary=(ROOT/'examples/uncertainty-v1-results.json').read_text().replace('"holdout": false','"holdout": true,"holdout": false')
        run=self.run_raw((raw+'\n').encode(),summary.encode());self.assertNotEqual(run.returncode,0);self.assertIn('duplicate JSON name',run.stderr)

    def test_conflicting_schedule_budget_and_terminal_are_rejected(self):
        for edit,reason in [
            (lambda r:r['journal']['genesis']['case']['peers'][0].update(work=8),'genesis schedule/budget'),
            (lambda r:r['journal']['genesis']['budget'].update(inspections=49),'genesis schedule/budget'),
            (lambda r:r['journal']['genesis'].update(clock='observation-clock-v1'),'genesis schedule/budget'),
            (lambda r:r['journal']['terminal']['measures'].update(primary_correct=False),'terminal state'),
            (lambda r:r['journal']['terminal']['measures'].update(primary_historical_misses=0),'terminal state')]:
            r=trace('Y');edit(r);self.rejected(r,reason)

    def test_resource_reason_is_checked_separately_from_matching_effects(self):
        rows=[trace('M','M','unavailable',facet) for facet in ('bypassed','neutral-cut')]
        run=self.run_rows(rows);self.assertEqual(run.returncode,0,run.stderr)
        for r in rows:self.assertEqual(r['measures']['credits_unrestored'],1)
        self.assertEqual([r['measures']['reprisal_imposed'] for r in rows],[1,0])
        r=deepcopy(rows[0]);r['events'][0]['reason']='nonpunitive-budget-cut';self.rejected(r,'resource reason')

    def test_extra_events_shifted_phases_and_forged_keeper_are_rejected(self):
        for edit,reason in [
            (lambda r:r['events'].append({'kind':'authority-grant','slot':20}),'unknown outer event'),
            (lambda r:r['events'][1].update(slot=5),'initial phase boundary'),
            (lambda r:r['events'].append({'kind':'execution','phase':'first','choice':'M','slot':20}),'duplicate first phase'),
            (lambda r:r['journal']['events'][2]['response']['review'].update(actor='worker'),'keeper receipt'),
            (lambda r:r['journal']['events'][1]['response'].update(proposal=99),'proposal receipt')]:
            r=trace();edit(r);self.rejected(r,reason)

    def test_hash_tampering_and_event_reordering_are_rejected(self):
        r=trace();r['journal']['events'][0]['hash']='0'*64
        run=self.run_rows([r]);self.assertNotEqual(run.returncode,0);self.assertIn('journal event hash',run.stderr)
        r=trace();r['journal']['events'][0],r['journal']['events'][1]=r['journal']['events'][1],r['journal']['events'][0]
        self.rejected(r,'command/outer phase linkage')

    def test_raw_bytes_are_hashed_without_newline_normalization(self):
        raw=(json.dumps(trace())+'\n').encode()
        for data in (raw,raw.replace(b'\n',b'\r\n')):
            run=self.run_raw(data);self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(run.stdout);self.assertEqual(result['episodes_sha256'],sha256(data).hexdigest());self.assertFalse(result['complete_matrix'])
        run=self.run_raw(raw.rstrip(b'\n'));self.assertNotEqual(run.returncode,0);self.assertIn('final newline',run.stderr)

    def test_input_limits_and_encoding(self):
        for raw,reason in [(b' '* (1024*1024+1),'oversized row'),(b'\xff\n','encoded data'),
                           (b'['*66+b']'*66+b'\n','nesting limit'),(b'{"n":9007199254740993}\n','unsafe JSON integer'),
                           (b'{"n":NaN}\n','JSON value')]:
            run=self.run_raw(raw);self.assertNotEqual(run.returncode,0);self.assertIn(reason,run.stderr)

    def test_scope_flags_cannot_claim_production_or_holdouts(self):
        r=trace();r['authority_granted']=True;self.rejected(r,'row scope')
        for key in ('production_ready','holdout','authority_granted'):
            summary=json.loads((ROOT/'examples/uncertainty-v1-results.json').read_text());summary[key]=True
            run=self.run_rows([trace()],json.dumps(summary).encode());self.assertNotEqual(run.returncode,0);self.assertIn('summary scope',run.stderr)

    def test_consistent_wrong_policy_label_is_explicitly_outside_scope(self):
        r=trace('M');r['policy']='constant-Y' # Accounting is unchanged; fixed policy choice is false.
        run=self.run_rows([r]);self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout);self.assertFalse(result['policy_verified']);self.assertFalse(result['evidence_authenticated']);self.assertFalse(result['authority_granted'])
        from commonwealth.uncertainty_v1.experiment import replay
        with self.assertRaises(ValueError):replay(r)

    def test_fixture_truth_and_origin_authenticity_are_explicitly_outside_scope(self):
        r=trace();r['evaluation']['actual_origins']=['a','a','a']
        r['evaluation']['packets'][0]['claim']='Y' # Unpurchased source content is an evaluator declaration.
        r['cell']['pattern']='agreement' # Domain is checked, correspondence to Python fixture is not.
        run=self.run_rows([r]);self.assertEqual(run.returncode,0,run.stderr)
        self.assertFalse(json.loads(run.stdout)['evidence_authenticated'])

    def test_scored_implementation_and_results_are_unchanged(self):
        manifest=json.loads((ROOT/'tests/data/uncertainty-audit-preserved-baseline.json').read_text())
        for name,expected in manifest['files'].items():
            with self.subTest(path=name):self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(),expected)
