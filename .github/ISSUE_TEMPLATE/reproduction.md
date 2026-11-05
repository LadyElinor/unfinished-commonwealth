---
name: Reproduction or independent check
about: Report a reproduced result, mismatch, blocked attempt or onboarding ambiguity.
title: "[Reproduction] "
---

## What did you check?

Name the result, component or instruction. English and Chinese reports are welcome.

## Exact version and environment

- Commit (`git rev-parse HEAD`):
- Local modifications (`git status --short`):
- OS and Python version:
- Node.js and optional dependency versions, if used:

## Method

Did you rerun the supplied code, independently implement the definitions, or use separately controlled evidence? Describe any access to the supplied answers or implementation.

## Commands and inputs

Include exact commands and synthetic inputs or public file paths. Keep the original failed-run evidence. Do not include credentials, private conversations or production databases.

## Expected and observed results

Include exit codes, summary comparisons and the smallest useful output. Record failures and mismatches alongside successes.

## Coverage and limits

Which checks passed, failed, were skipped or were blocked? Was the separate UID-isolation demonstration actually run? Do not treat readiness exit 2 / LOCAL_RESEARCH_ONLY as a failed test.

## First unclear instruction or proposed correction

If proposing changed rules, budgets, controls or reference arithmetic, explain the effect on the original claim. Keep new experiments separate from frozen results.
