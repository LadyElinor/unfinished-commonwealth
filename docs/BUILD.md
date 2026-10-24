# Build, validate, and restore the repository

## Runtime

Python 3.11 or later is required. Runtime code and behavioral tests use only the
standard library. From the checkout root:

```bash
python scripts/verify.py
python scripts/reproduce.py .local/reproduction
python -m commonwealth verify .local/reproduction/demo.sqlite
```

Choose a new output path for every reproduction. Existing databases, report
files, and release directories are never deliberately overwritten. Inspect a
partial output after a failed build before choosing another new directory.

The reproduction creates a five-tick demonstration, its JSON event record and
summary, and all twelve exposed scripted comparisons. `readiness` returns exit
code 2 by design; it is not a failing installation test.

## Offline package check

With setuptools>=68, wheel, pip, and venv already available locally:

```bash
python scripts/package.py .local/release
```

This command:

1. Builds a source archive containing code, tests, examples, and documentation.
2. Extracts that archive into a temporary directory and runs its checks.
3. Builds the wheel from the extracted source, not the original checkout.
4. Installs the wheel into a fresh virtual environment with `--no-index`.
5. Runs both installed entry points outside the checkout, verifies packaged data,
   replays the 24-event demonstration, and runs all twelve comparisons.
6. Writes the wheel, source archive, and `package-verification.json` into the
   chosen output directory.

No API key, model account, or remote repository is needed. If build tools are
missing, install them from your normal approved package source before running
this check; the script will not fetch or install build dependencies itself.
This checks the current interpreter and platform, not every supported platform.

## Repository delivery

The complete repository delivery ZIP contains source files, a verified release
directory, and a `source-history.bundle` with local Git history. Generated
workshop databases, private input files, caches, and virtual environments are
not bundled. The full supplied manuscript is not redistributed.

To restore the exact local Git repository from the extracted ZIP:

```bash
git clone source-history.bundle commonwealth-checkout
cd commonwealth-checkout
git log --oneline
python scripts/verify.py
```

Run the clone command from the directory containing the bundle and choose a
fresh checkout path. The bundle preserves the imported 0.1.0 source as the first
commit, followed by the hardening/build changes. It is not a GitHub publication;
no origin remote, hosted CI run, merge, or deployment is implied.

The delivery's `DELIVERY.json` identifies the final commit and artifact hashes.
The archive is a separate release copy; it does not replace the user's inputs.

## Replay compatibility

Package releases through 0.1.1 used unversioned envelopes, journal schema 1,
and historical state `version: "0.1.0"`. Release 0.1.2 replays those events
with `commonwealth/legacy_v1.py` and leaves their hashes unchanged. New events
use `protocol: 2`; the first accepted new event atomically upgrades the state
to schema 2. A read or refused command makes no change. Historical fixtures
in `tests/data/` were exported by 0.1.1 before changing the implementation.
They include a successor execution without observation, which must replay
historically even though new v2 commands enforce observation.

The new demo has a new hash because new envelopes and testimony differ.
Do not substitute a freshly generated demo for the frozen historical fixtures.
Do not edit the legacy reducer to change live behavior. Unknown versions,
protocol downgrades, malformed JSON, and type-substituted records are refused.
See [protocol compatibility](PROTOCOL.md). Older packages cannot read v2
events; back up an old database before continuing it with the new version.
