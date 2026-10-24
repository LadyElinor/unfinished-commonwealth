# Validation evidence

## Release 0.1.2

Validated locally on 23 October 2026 (America/New_York), using CPython 3.12.14
on Linux. The complete suite has 84 passing tests: the prior 65 checks, with
the historical-demo check changed to read an actual frozen 0.1.1 journal,
plus 19 priority regression tests.

The added cases cover every coached scenario's factual testimony, on-time peer
accounts, reflection's command-only cost, direct and evidence-linked disputes,
review/retirement history, new challenges after retention, keeper-only review,
fresh successor observations and separate approval, the full operational/review
boundary, unresolved closeout records, refused-command rollback, old journals
at their previous ceiling, historical unobserved successors, and strict protocol
tags/downgrade refusal. Additional cases reproduce the positive-only lesson
transfer into signed data and verify chronological selection across numeric
event-ID boundaries, including fallback when the newest lesson is suspended.

Both frozen historical fixtures were exported by the unmodified 0.1.1 code
before implementation. The historical demonstration retains its original head;
the new demonstration has 24 events, five observed ticks, the same recorded
missed deadline, and no pending peer jobs. All twelve scripted comparisons
complete. Their environmental outcomes retain the original limitations.

The source distribution, extracted-source test suite, wheel built from that
source, and offline clean-environment CLI/module entry points are checked with
`scripts/package.py`. See the exact published commit's hosted CI for platform
results. This local record does not by itself certify Windows or other Python
versions. The original 0.1.1 validation record is retained below.

## Release 0.1.1 historical record

Validated locally on 24 October 2026 using CPython 3.12.14 on Linux x86-64.
Packaging used setuptools 84.1.0 and wheel 0.48.0. These are observed build-tool
versions, not added runtime dependencies or claims of bit-identical builds.

## Completed checks

| Check | Result |
| --- | --- |
| Supplied 0.1.0 behavioral baseline | 46 tests passed before changes |
| Final behavioral, adversarial, and packaging suite | 65 tests passed |
| Packaged JSON and local documentation links | Passed |
| Compile all package, script, and test modules | Passed |
| `git diff --check` | Passed |
| Five-tick repair/succession demonstration | 24 events replayed |
| Exposed scripted comparison | All 12 runs completed |
| Source distribution | Built; extracted-source checks passed |
| Wheel built from source distribution | Built; fixture data included |
| Clean virtual-environment install | Passed without network resolution |
| Installed CLI and module entry points | Both exercised outside checkout |
| Installed demo and comparison | 24 events / 12 runs verified |
| Research-only readiness | Expected exit 2; deployment_ready=false |

## Regression coverage added

Fourteen new tests cover oversized integer probabilities, nonfinite JSON forms,
excessive nesting and its boundary, duplicate nested keys, actual byte-size and
multibyte limits, bounded reads without trustworthy metadata, strict snapshot
and result types, integer sequence fields, malformed journal/snapshot JSON,
fixture description limits, and historical replay compatibility.

Five packaging tests additionally check regular extraction, aliased temporary
roots, parent traversal, absolute paths, and rejection of symbolic/hard links.
The first hosted matrix passed all behavioral tests and reproductions on every
platform, but exposed a Windows temporary-path alias mismatch in the new
packaging script. Both the extraction root and candidate paths are now resolved
before the containment check; traversal and link protections remain in place.
Consult the exact commit's hosted checks for the final cross-platform result.

Rejected commands are checked against an unchanged verified journal. Adversarial
stored-result tests recompute envelope hashes before verification, ensuring the
replay check detects the inconsistent result rather than merely an old hash.

## Retained behavior

The baseline and final demonstration share journal head
`8c462114644fb93db2347d25ded1d8be77829289e6be71394cbc9e411ebb09b8`.
The final state has five observed ticks, one historical missed peer deadline,
five completed peer jobs, no pending peer work, and a successor applying the
scoped quality-flags practice. The earlier loss is not erased.

The full source delivery includes `release/package-verification.json` with the
installed-package results. To reproduce checks, follow [BUILD.md](BUILD.md).

## Limits

- Only Python 3.12.14 on Linux was executed for this local report. The CI workflow
  configures Python 3.11, 3.12, and 3.13 on Linux plus 3.12 on Windows. Its presence
  is not evidence that remote CI ran; consult the exact published commit's checks
  separately when a remote repository is available.
- No model-backed study, held-out evaluation, independent participant identity,
  external execution adapter, production authentication, or deployment was run.
- This is a bounded correctness review, not a comprehensive security audit.
- All included comparisons remain scripted, exposed, and synthetic. They do not
  establish causal benefits from coaching, stories, or decentralization.
