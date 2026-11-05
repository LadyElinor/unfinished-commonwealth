# C2 standalone participant client

This separately built distribution includes only the bounded loopback client,
wire helpers and durable outbox. It does not include workshop, keeper, host,
evaluator, fixture data or host demos. Python 3.11+ and its standard library
are required. No third-party runtime dependencies.

Use `python -m commonwealth_client_v2 --help` or `commonwealth-client --help`.
Commands: `stage`, `status`, `resolve`, `retry`. There is no host installation,
credential issuance, execution or demo command. Use an operator-managed B1.1
host and a separately supplied capability/task/request. C1 files are not
silently migrated: retain them with the historical C1 client. Never recreate
an uncertain old intent under a new request ID or replacement capability.

Artifact separation is not OS isolation or evidence secrecy. All historic
fixtures are public. The host and local storage remain trusted, accepted
receipts can be forged by the host, and cached records are historical rather
than current authorization. Lookup alone cannot bind original request bytes;
explicit exact-byte retry is required to record the outcome. No model efficacy,
independent holdout, power-loss durability or production-security claim.

See the repository `docs/CLIENT_ONLY_V2.md` for the artifact verification and
limits. Source ancestry: C1/B1 at commit 54199f7982291d585d62caf7d1517235362d4ffe.
