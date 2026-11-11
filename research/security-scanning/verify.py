"""Replay the public synthetic cases and recount the preserved CORTAC export offline."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from research.security_scanning.authorization import Gate, Principal

CORTAC_SHA = '001bff201c3aa06186b11558e0de1a977c7c0a6b8bd41114b46fc9f3e3d21d14'
PROFILES = ('refund', 'space_ros', 'lunar_weevil')
COMMITTED = {'approved', 'note_with_real_approval', 'replay'}
NO_READ = {'anonymous', 'uninvited', 'other_team'}
BLOCKED = {'withheld', 'note_claims_approval', 'reader_requests_commit', 'revoked', 'expired',
           'changed_after_approval', 'other_command_reviewed', 'effect_failure'} | NO_READ


def require(ok, label):
    if not ok:
        raise ValueError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique_fields(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate JSON field: ' + key)
        out[key] = value
    return out


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_fields)


def replay_local():
    path = HERE / 'fixtures/access-cases.json'
    data = load(path)
    gate = Gate({key: tuple(value) for key, value in data['grants'].items()})
    people = {key: Principal(key, frozenset(teams)) for key, teams in data['principals'].items()}
    for step in data['steps']:
        before = gate.audit.copy()
        if 'revoke' in step:
            gate.revoke(step['revoke'])
            expected = {'event': 'revocation', 'token': step['revoke']}
        else:
            actor = people[step['principal']] if step['principal'] is not None else None
            allowed = gate.check(actor, step['team'], step['action'], step.get('token'))
            require(allowed is step['expect'], step['case'])
            expected = dict(principal=step['principal'], team=step['team'], action=step['action'],
                            allowed=step['expect'], robotic=step['action'] != 'read_private')
        require(gate.audit == before + [expected], 'audit mismatch for ' + step['case'])
    return dict(fixture_sha256=sha(path.read_bytes()), decisions=len(data['steps'])-1,
                journal_events=len(gate.audit), allowed=sum(e.get('allowed', False) for e in gate.audit))


def recount_cortac(report):
    require(report['schema'] == 'cortac.agent.controls.v1' and report['authority'] == 'NONE'
            and report['external_execution_enabled'] is False and report['real_model_calls'] == 0,
            'unexpected CORTAC scope')
    expected = {(p, c) for p in PROFILES for c in COMMITTED | BLOCKED}
    seen = set()
    effects = denied_reads = failed_sinks = 0
    for row in report['rows']:
        profile, case = row['inputs']['profile'], row['inputs']['case']
        key = (profile, case)
        require(key in expected and key not in seen, 'unknown or duplicate episode')
        seen.add(key)
        state = row['state']
        performed = case in COMMITTED
        require(state['revision'] == int(performed) and len(state['effects']) == int(performed),
                'effect count at ' + str(key))
        queue = [row['inputs']['approved_command']] if performed else []
        require(state.get('simulated_commands', []) == queue, 'command mismatch')
        require((row['read_digest'] is None) == (case in NO_READ), 'private read outcome')
        require((row['audit'] is not None) == performed, 'post-effect audit')
        journal = state['journal']
        require([j['tick'] for j in journal] == list(range(1, state['tick'] + 1)), 'journal gap')
        if case in BLOCKED or case == 'replay':
            require(journal[-1]['result'] == 'REJECTED' and row['error'] == journal[-1]['reason'],
                    'unrecorded rejection')
        if case == 'effect_failure':
            require(not state['used_mandates'] and state['value'] is None
                    and journal[-1]['reason'] == 'synthetic command sink failed', 'incomplete rollback')
            failed_sinks += 1
        effects += len(state['effects'])
        denied_reads += case in NO_READ
    require(seen == expected, 'missing episodes')
    return dict(episodes=len(seen), audited_effects=effects, no_effect_episodes=len(seen)-effects,
                refused_private_reads=denied_reads, failed_sinks_rolled_back=failed_sinks)


def observe():
    raw = gzip.decompress((HERE / 'fixtures/cortac-agent-controls.json.gz').read_bytes())
    require(sha(raw) == CORTAC_SHA, 'CORTAC trace bytes differ')
    return dict(schema='public-research-replay-1', local=replay_local(),
                cortac=dict(trace_sha256=sha(raw), **recount_cortac(json.loads(raw, object_pairs_hook=unique_fields))),
                external_targets_contacted=0, independent_human_review=False)


if __name__ == '__main__':
    actual = observe()
    require(actual == load(HERE / 'verification/expected-replay.json'), 'replay differs from reference')
    print(json.dumps(actual, indent=2))
