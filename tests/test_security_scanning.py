"""Offline regression and provenance checks for the public research register."""
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

from research.security_scanning.authorization import Gate, Principal

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'research/security-scanning'
spec = importlib.util.spec_from_file_location('public_scan_replay', DATA / 'verify.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class ResearchScanTests(unittest.TestCase):
    def test_action_classification_cannot_be_relaxed(self):
        gate = Gate({'only-move': ('alice', 'alpha', 'move_simulated')})
        alice = Principal('alice', frozenset({'alpha'}))
        for flag in (False, True):
            self.assertFalse(gate.check(alice, 'alpha', 'move_simulated', robotic=flag))
            self.assertTrue(gate.audit[-1]['robotic'])
        self.assertFalse(gate.check(alice, 'alpha', 'arbitrary', 'only-move'))
        self.assertTrue(gate.check(alice, 'alpha', 'read_private'))
        self.assertTrue(gate.check(alice, 'alpha', 'move_simulated', 'only-move'))
        gate.revoke('only-move')
        self.assertFalse(gate.check(alice, 'alpha', 'move_simulated', 'only-move'))

    def test_two_benchmark_recounts(self):
        self.assertEqual(replay.observe(), replay.load(DATA / 'verification/expected-replay.json'))

    def test_recount_rejects_lost_evidence(self):
        source = json.loads(gzip.decompress((DATA / 'fixtures/cortac-agent-controls.json.gz').read_bytes()))
        for mode in ('duplicate', 'rollback', 'disclosure'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                changed = deepcopy(source)
                if mode == 'duplicate':
                    changed['rows'][0] = changed['rows'][1]
                elif mode == 'rollback':
                    failed = next(r for r in changed['rows'] if r['inputs']['case'] == 'effect_failure')
                    failed['state']['used_mandates'].append('initial')
                else:
                    denied = next(r for r in changed['rows'] if r['inputs']['case'] == 'anonymous')
                    denied['read_digest'] = 'returned record'
                replay.recount_cortac(changed)

    def test_records_resolve_to_sources_and_artifacts(self):
        register = replay.load(DATA / 'citation-register.json')
        sources = {r['id']: r for r in register}
        self.assertEqual(len(sources), len(register))
        self.assertEqual(sources['GS-02']['derived_from'], ['GS-01'])
        for record in replay.load(DATA / 'findings.json'):
            ids = record['citation_ids']
            self.assertTrue(ids and set(ids) <= sources.keys())
            for k, v in record['source'].items():
                self.assertEqual(sources[ids[0]][k], v)
            if record.get('artifact_path'):
                path = (DATA / record['artifact_path']).resolve()
                self.assertTrue(path.is_relative_to(DATA))
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['artifact_sha256'])
        for row in replay.load(DATA / 'source-inventory.json')['repositories']:
            self.assertIn(row['citation_id'], sources)
        for query in replay.load(DATA / 'discovery.json')['queries_used']:
            self.assertTrue(set(query['citation_ids']) <= sources.keys())

    def test_priority_matrix_preserves_reference_scores(self):
        html = (DATA / 'priority-matrix.html').read_text(encoding='utf-8')
        embedded = re.search(r'<script type="application/json" id="reference">(.*?)</script>', html).group(1)
        self.assertEqual(json.loads(embedded), replay.load(DATA / 'priorities.json'))

    @unittest.skipUnless(importlib.util.find_spec('jsonschema'), 'optional JSON Schema validator')
    def test_finding_contract_and_independence_rule(self):
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import ValidationError
        schema = replay.load(DATA / 'finding.schema.json')
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        records = replay.load(DATA / 'findings.json')
        for record in records:
            validator.validate(record)
        record = deepcopy(records[0])
        record['verification']['independent_reproduction'] = True
        with self.assertRaises(ValidationError):
            validator.validate(record)
