"""Exposed maintenance applicability/review checks against an exact CORTAC checkout."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'examples/maintenance_v1'
BASE = '3688dcdfa70b27531c8f0d3bd315a88736c87655'
CORTAC = 'ea7a72456e00bd2b80aa4ccd9ae97262aedc3562'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def refused(call):
    try:
        call()
    except ValueError:
        return True
    raise ValueError('negative control was accepted')


def probes(output, baseline):
    old = git(ROOT, 'show', BASE + ':scripts/verify.py')
    need(hashlib.sha256(old).hexdigest() == baseline['verifier_sha256'], 'baseline source changed')
    rows = []
    for case in baseline['cases']:
        for version in ('baseline', 'candidate'):
            modes = (False, True) if version == 'candidate' and case['case'] == 'mixed' else (False,)
            for strict in modes:
                with tempfile.TemporaryDirectory(prefix='commonwealth-maintenance-') as temporary:
                    root = Path(temporary)
                    for name in ('scripts', 'tests', 'docs'):
                        (root / name).mkdir()
                    for name in ('README.md', 'ROADMAP.md', 'CONTRIBUTING.md'):
                        (root / name).write_text('Exposed maintenance fixture.\n', encoding='utf-8')
                    if case['fixture_source']:
                        (root / 'tests/test_probe.py').write_text(case['fixture_source'], encoding='utf-8')
                    if version == 'baseline':
                        (root / 'scripts/verify.py').write_bytes(old)
                    else:
                        for name in ('verify.py', 'verification_tests.py'):
                            shutil.copyfile(ROOT / 'scripts' / name, root / 'scripts' / name)
                    args = [sys.executable, str(root / 'scripts/verify.py')]
                    if version == 'candidate':
                        args += ['--report', str(root / 'receipt.json')]
                    if strict:
                        args.append('--require-no-skips')
                    started = time.perf_counter_ns()
                    run = subprocess.run(args, cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
                    row = dict(case=case['case'], version=version, require_no_skips=strict,
                               exit_code=run.returncode, elapsed_ns=time.perf_counter_ns()-started)
                    log = run.stdout + run.stderr
                    label = f"{version}-{case['case']}-{'strict' if strict else 'default'}"
                    (output / (label + '.log')).write_text(log, encoding='utf-8')
                    row['log_sha256'] = sha(output / (label + '.log'))
                    if version == 'candidate':
                        receipt = json.loads((root / 'receipt.json').read_text(encoding='utf-8'))
                        row['status'] = receipt['status']
                        expected = 'FAILED' if case['case'] in ('empty', 'all-skipped', 'failure') or strict else (
                            'PASSED_WITH_SKIPS' if case['case'] == 'mixed' else 'PASSED')
                        need(receipt['status'] == expected, 'candidate fixture mismatch: ' + label)
                        need(run.returncode == (1 if expected == 'FAILED' else 0), 'candidate exit mismatch')
                        (output / (label + '.json')).write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
                    elif case['case'] in ('all-skipped', 'pass', 'mixed'):
                        need(run.returncode == 0, 'baseline positive/skip control changed')
                    elif case['case'] == 'failure':
                        need(run.returncode != 0, 'baseline failure control changed')
                    # Empty-discovery baseline behavior is Python-version-dependent;
                    # retain what happened instead of forcing the initial diagnosis.
                    rows.append(row)
    return rows


def run(cortac, output):
    output.mkdir(parents=True, exist_ok=False)
    binding = json.loads((DATA / 'binding.json').read_text(encoding='utf-8'))
    need(binding['baseline_commit'] == BASE and binding['cortac_commit'] == CORTAC, 'pin mismatch')
    for group in ('candidate', 'preserved'):
        for path, expected in binding[group].items():
            need(sha(ROOT / path) == expected, 'changed bound file: ' + path)
    need(git(cortac, 'rev-parse', 'HEAD').decode().strip() == CORTAC, 'wrong CORTAC commit')
    need(not git(cortac, 'status', '--porcelain').strip(), 'CORTAC checkout is modified')
    sys.path.insert(0, str(cortac / 'package'))
    from wac_offline.decision_records import validate_decision_record
    from wac_offline.scaffold_v1 import ap1

    limits = json.loads((DATA / 'protected_limits.json').read_text(encoding='utf-8'))
    record = json.loads((DATA / 'review.json').read_text(encoding='utf-8'))
    evidence = {'baseline', 'candidate', 'plan', 'regressions'}
    def refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'evidence_refs':
                    need(set(value) <= evidence, 'unresolved supplied evidence reference')
                else:
                    refs(value)
        elif isinstance(obj, list):
            for value in obj:
                refs(value)
    refs(record)
    need(validate_decision_record(record, limits) is False, 'UNKNOWN review was promoted')
    controls = {}
    repository_task = {'schema': 'commonwealth.repository-change.v1', 'base': BASE,
                       'proposal_binding': sha(DATA / 'binding.json')}
    controls['repository_task_refused'] = refused(lambda: ap1.brief(repository_task, profile=ap1.PROFILE_1_1))
    workshop = json.loads((ROOT / 'examples/agent_profile_v1/example_task.json').read_text(encoding='utf-8'))
    brief = ap1.brief(workshop, profile=ap1.PROFILE_1_1)
    response = dict(profile=brief['profile'], brief_id=brief['brief_id'], choice='apply-patch', patch='out-of-scope')
    controls['patch_action_refused'] = refused(lambda: ap1.interpret(brief, response))
    response = dict(profile=brief['profile'], brief_id=brief['brief_id'], choice='propose', method='apply-patch',
                    prediction=dict(primary_correct=1, peer_on_time=1), purpose='Negative scope control.')
    controls['patch_method_refused'] = refused(lambda: ap1.interpret(brief, response))
    missing = deepcopy(record); del missing['alternatives']
    controls['missing_field_refused'] = refused(lambda: validate_decision_record(missing, limits))
    controls['removed_limit_refused'] = refused(lambda: validate_decision_record(record, limits[:-1]))
    erased = deepcopy(record); erased['dissent'] = []
    controls['erased_dissent_refused'] = refused(lambda: validate_decision_record(erased, limits))
    failed = deepcopy(record); failed['protected_limit_assessments'][0]['status'] = 'FAIL'
    controls['fail_not_promoted'] = validate_decision_record(failed, limits) is False
    positive = deepcopy(record)
    for assessment in positive['protected_limit_assessments']:
        assessment['status'] = 'PASS'
    controls['fabricated_all_pass_is_structurally_accepted'] = validate_decision_record(positive, limits) is True
    # This accepted negative epistemic control matters: completeness cannot
    # determine whether a claimed independent review actually occurred.
    need(all(controls.values()), 'review control failed')
    baseline = json.loads((DATA / 'baseline.json').read_text(encoding='utf-8'))
    rows = probes(output, baseline)
    report = dict(schema='commonwealth.cortac-maintenance.v1', baseline_commit=BASE, cortac_commit=CORTAC,
                  binding_sha256=sha(DATA / 'binding.json'), review_sha256=sha(DATA / 'review.json'),
                  controls=controls, verifier_probes=rows, preserved_files=len(binding['preserved']),
                  review_structurally_complete=True, supplied_assessments_pass=False,
                  s2_scheduling='NOT_ATTEMPTED_NO_ADMITTED_REPOSITORY_TASK',
                  authority='NONE', scope='LOCAL_RESEARCH_ONLY', independent_review=False,
                  efficacy_measured=False, autonomous_patch_generation=False,
                  agent_latency_tokens_money='NOT_MEASURED', python=sys.version.split()[0])
    (output / 'results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cortac', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        run(args.cortac.resolve(), args.output.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('MAINTENANCE_PILOT_REFUSED: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
