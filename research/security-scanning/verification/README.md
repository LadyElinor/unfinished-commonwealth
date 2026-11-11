# Verification and independent review

From the Unfinished Commonwealth repository root, run the local decision checks and the cross-project recount.

```bash
python -m unittest research.security_scanning.test_authorization -v
python research/security-scanning/verify.py
python scripts/verify.py
```

The first benchmark uses one synthetic private read and one simulated movement operation. A trusted harness supplies the test principals. The gate itself chooses which operations require a grant. The fixture exercises eight decisions plus one revocation. It includes same-team success, unsigned and uninvited requests, a cross-team request, and a command both before and after revocation. The log is an in-memory record.

The CORTAC snapshot contains all 42 raw episodes from [PR 8, exact revision](https://github.com/LadyElinor/CORTAC/tree/75fd8f979502eb9f81ce380577939c9c3ec33dc7). Each uses a newly created local SQLite gateway. The included gzip member holds the original producer's UTF-8 JSON bytes. Its uncompressed SHA-256 is `001bff201c3aa06186b11558e0de1a977c7c0a6b8bd41114b46fc9f3e3d21d14`. The companion [license](../fixtures/CORTAC-LICENSE.txt) accompanies the preserved fixture. The local recount checks the expected episode inventory, record delivery, effects, command contents, rollback and rejection journals. The original CORTAC checker also reconciles individual approval receipts.

To repeat the full producer on a clean CORTAC checkout at the pinned revision, run the following from that checkout. The Python writer preserves UTF-8 and LF across platforms.

```bash
python -c "import pathlib,subprocess,sys; pathlib.Path('agent-controls.json').write_bytes(subprocess.check_output([sys.executable,'scripts/agent_integration.py']).replace(b'\r\n',b'\n'))"
python scripts/check_agent_controls.py agent-controls.json
python -c "import pathlib,hashlib; print(hashlib.sha256(pathlib.Path('agent-controls.json').read_bytes()).hexdigest())"
```

The [expected replay](expected-replay.json) is an observed same-author rerun and separate checker implementation. The [robot interface observations](robot-checks.json) are preserved from the earlier pinned run. That run round-tripped a Nav2 goal and completed two simulated seconds of a single-leg MuJoCo trace. This scan rechecked the authorization export. It did not rerun either robot backend.

An independent reviewer can record their commit, operating system, interpreter, input and output digests, commands, observed differences, and the scope of their independence. The reviewer field and independent-reproduction flag should change only after that evidence arrives. Artifact hashes compare bytes. They provide neither a signature nor an external chain of custody.
