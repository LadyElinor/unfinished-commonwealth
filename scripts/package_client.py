"""Build C2 offline; reject extra artifact files; test isolated installed client.

The test host runs in this trusted builder, not in the client environment.
Artifact separation is neither a hostile-code sandbox nor hidden evaluation.
"""
import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('__init__.py', '__main__.py', 'wire.py', 'transport.py', 'store.py', 'LICENSE.txt')
PACKAGE = 'commonwealth_client_v2'
DIST = 'unfinished_commonwealth_client-2.0.0'


def run(args, cwd, expected=0):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    p = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=120)
    if p.returncode != expected:
        raise RuntimeError(f'command failed: {args!r}\n{p.stdout}\n{p.stderr}')
    return p.stdout


def check_source(name, raw):
    # The archive may only contain the reviewed standalone sources. This extra
    # import gate rejects accidental reintroduction of host or external imports.
    tree = ast.parse(raw, filename=name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [a.name.split('.')[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            modules = [(node.module or '').split('.')[0]]
        else:
            continue
        if any(n not in sys.stdlib_module_names for n in modules):
            raise ValueError(f'non-stdlib dependency in {name}')


def validate_wheel(path, source):
    runtime = {f'{PACKAGE}/{n}' for n in FILES}
    metadata = {f'{DIST}.dist-info/{n}' for n in ('METADATA', 'WHEEL', 'entry_points.txt', 'top_level.txt', 'RECORD')}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != runtime | metadata:
            raise ValueError('unexpected client wheel members')
        for n in FILES:
            data = z.read(f'{PACKAGE}/{n}')
            if data != (source / 'src' / PACKAGE / n).read_bytes():
                raise ValueError('wheel source mismatch')
            if n.endswith(".py"):
                check_source(n, data)
        if BytesParser().parsebytes(z.read(f'{DIST}.dist-info/METADATA')).get_all('Requires-Dist'):
            raise ValueError('client wheel has runtime dependencies')
    return sorted(names)


def extract_client(path, dest):
    expected = {'README.md', 'pyproject.toml', 'PKG-INFO', 'setup.cfg'}
    expected |= {f'src/{PACKAGE}/{n}' for n in FILES}
    expected |= {f'src/unfinished_commonwealth_client.egg-info/{n}' for n in
                 ('PKG-INFO', 'SOURCES.txt', 'dependency_links.txt', 'entry_points.txt', 'top_level.txt')}
    with tarfile.open(path) as archive:
        files = [m for m in archive.getmembers() if m.isfile()]
        names = [m.name for m in files]
        if len(names) != len(set(names)) or set(names) != {f'{DIST}/{n}' for n in expected}:
            raise ValueError('unexpected client source archive members')
        # Directories must also remain within the exact expected parents.
        dirs = {str(p) for n in names for p in PurePosixPath(n).parents if str(p) != '.'}
        if any(not m.isfile() and (not m.isdir() or m.name not in dirs) for m in archive.getmembers()):
            raise ValueError('unexpected client source archive entry')
        for m in files:
            target = dest / m.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(m) as incoming:
                target.write_bytes(incoming.read())
    return dest / DIST, sorted(names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    args = parser.parse_args()
    output = Path(args.directory).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='commonwealth-client-') as t:
        temp = Path(t).resolve()
        # Build from an exact clean allowlist, not stale build/egg-info files.
        source = temp / 'build-source'
        (source / 'src' / PACKAGE).mkdir(parents=True)
        for name in ('README.md', 'pyproject.toml', *(f'src/{PACKAGE}/{n}' for n in FILES)):
            (source / name).write_bytes((ROOT / 'client_dist' / name).read_bytes())
        run([sys.executable, '-c', 'from setuptools.build_meta import build_sdist; import sys; build_sdist(sys.argv[1])', str(output)], source)
        archives = list(output.glob('*.tar.gz'))
        if len(archives) != 1:
            raise ValueError('expected one client source archive')
        extracted, source_members = extract_client(archives[0], temp / 'extracted')
        run([sys.executable, '-c', 'from setuptools.build_meta import build_wheel; import sys; build_wheel(sys.argv[1])', str(output)], extracted)
        wheels = list(output.glob('*.whl'))
        if len(wheels) != 1:
            raise ValueError('expected one client wheel')
        wheel_members = validate_wheel(wheels[0], source)
        venv = temp / 'venv'
        run([sys.executable, '-m', 'venv', str(venv)], temp)
        python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        run([str(python), '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', '--no-cache-dir', str(wheels[0])], temp)
        smoke = temp / 'client-cwd'
        smoke.mkdir()
        command = venv / ('Scripts/commonwealth-client.exe' if os.name == 'nt' else 'bin/commonwealth-client')
        if '{stage,status,resolve,retry}' not in run([str(command), '--help'], smoke):
            raise ValueError('installed client entry point mismatch')
        graph = json.loads(run([str(python), '-I', '-c', "import json, sys, importlib.util; import commonwealth_client_v2.__main__; assert importlib.util.find_spec('commonwealth') is None; print(json.dumps(sorted(n for n in sys.modules if n.startswith('commonwealth'))))"], smoke))
        if graph != sorted([PACKAGE, *(PACKAGE + '.' + n[:-3] for n in FILES if n.endswith('.py') and n != '__init__.py')]):
            raise ValueError('unexpected installed import graph')
        # Host imports exist only in the builder. The client has no repository
        # path in sys.path and no host package installed.
        sys.path.insert(0, str(ROOT))
        from commonwealth.store import Workshop
        from commonwealth.participant_v1_1.store import Boundary
        from commonwealth.participant_v1.store import read_credential
        from commonwealth.participant_v1.transport import Server
        workshop = Workshop.create(temp / 'host.sqlite')
        boundary = Boundary(workshop.path)
        boundary.install()
        boundary.issue(temp / 'credential', ttl=120)
        token = read_credential(temp / 'credential')
        task = boundary.task(token)[1]
        packet = {'protocol': task['protocol'], 'request_id': 'installed-c2', 'view_head': task['view_head'], 'proposal': task['task']['proposal_example']}
        (temp / 'task.json').write_text(json.dumps(task), encoding='utf-8')
        (temp / 'request.json').write_text(json.dumps(packet), encoding='utf-8')
        server = Server(boundary)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        try:
            base = [str(python), '-I', '-m', PACKAGE]
            outbox = str(smoke / 'intent.sqlite')
            stage = json.loads(run(base + ['stage', outbox, server.url, str(temp / 'credential'), str(temp / 'task.json'), str(temp / 'request.json')], smoke))
            lookup = json.loads(run(base + ['resolve', outbox, str(temp / 'credential')], smoke, expected=3))
            accepted = json.loads(run(base + ['retry', outbox, str(temp / 'credential')], smoke))
            cached = json.loads(run(base + ['retry', outbox, str(temp / 'credential')], smoke))
            audit = boundary.audit()
            if (stage['state'] != 'UNRESOLVED' or lookup['state'] != 'UNRESOLVED'
                    or accepted['state'] != 'RECORDED' or cached != accepted
                    or accepted['recorded']['receipt']['permits_execution'] is not False
                    or audit['events'] != 2 or audit['capabilities'][0]['used'] != 1):
                raise ValueError('installed recovery gate failed')
            run(base + ['demo'], smoke, expected=2)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        report = {'scope': 'CLIENT_ARTIFACT_SEPARATION_ONLY', 'verified': True,
                  'source_members': source_members, 'wheel_members': wheel_members,
                  'installed_imports': graph, 'host_module_absent': True,
                  'host_boundary': 'participant-1.1.0', 'events': audit['events'],
                  'server_attempts': audit['capabilities'][0]['used'], 'model_calls': 0,
                  'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (*archives, *wheels)}}
        (output / 'client-package-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
