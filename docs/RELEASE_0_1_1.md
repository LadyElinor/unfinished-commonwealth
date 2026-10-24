# Release 0.1.1

This maintenance release preserves the original 0.1.0 workshop and fixes concrete
malformed-input and replay-integrity defects. It does not add new authority,
autonomous execution, model adapters, or a deployment capability.

## Correctness fixes

- Reject oversized integer probabilities as ordinary structured CLI refusals,
  rather than allowing `math.isfinite` to raise an uncaught overflow.
- Compare replayed results and snapshots using canonical JSON, not Python's
  permissive equality between booleans, integers, and floating-point numbers.
- Require actual integer journal sequence numbers.
- Reject duplicate JSON keys, nonfinite numbers (including overflowing decimal
  exponents), and nesting deeper than 64 containers at input/replay boundaries.
- Bound fixture descriptions to the documented nonempty 4,000-character text
  contract.
- Enforce the 64 KiB command-file limit on the bytes actually read, not only file
  metadata checked before reading.

Rejected commands do not commit state or accepted events. Malformed persisted
records report journal corruption. A host owner can still rewrite a whole
internally consistent history; these checks are not authentication or independent
attestation.

## Build and distribution

The source distribution explicitly includes tests, examples, scripts, and
documentation. `scripts/package.py` builds that distribution, validates the
extracted source, builds the wheel from it, and checks both installed entry
points in a clean virtual environment without network dependency resolution.
The CI matrix now includes this package check after behavioral and reproduction
checks. Configured CI is not evidence of a successful hosted run.

## Compatibility

Journal schema 1 and its historical state-version field remain unchanged. The
original five-tick demonstration still has 24 events and head
`8c462114644fb93db2347d25ded1d8be77829289e6be71394cbc9e411ebb09b8`.
Valid historical journals replay unchanged. Previously tolerated malformed
records are rejected, not silently migrated.

See [validation evidence](VALIDATION.md), [build instructions](BUILD.md), and the
unchanged [trust boundary](THREAT_MODEL.md). The original release record remains
available in [release 0.1.0](RELEASE_0_1_0.md).
