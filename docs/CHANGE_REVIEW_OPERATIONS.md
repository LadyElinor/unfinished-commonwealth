# Operate the Change Review service

Change Review is the first Commonwealth service for a real workload. A local submitter records a proposed software change and its evidence. A different local reviewer records approval or a decline with a rationale. Neither decision invokes a tool, merges a pull request or deploys software. The operating profile is one trusted Linux host, one operator, local accounts, bounded noncritical records and one active writer. The historical workshop, B1.1/C2 and O1 keep their existing interfaces and readiness reports.

The candidate distribution is `unfinished-commonwealth 0.1.4rc3`. The service has its own `change-review-1` schema, CLI and register. The packaged unit uses systemd, a Linux Unix-domain socket, a private local SQLite database and the kernel-reported peer UID. Anyone administering the host or controlling the service account is trusted. A digest identifies the submitted content inside this trust boundary. It does not verify the cited evidence or identify a person behind a shared account.

## Select the initial host

Use a dedicated, non-root service account called `commonwealth-review` with primary group of the same name. Give the chosen submitter and reviewer separate, non-root accounts and access to that group. The service account must be distinct from both. Grant clients traverse access to the runtime directory and connect access to the socket. Keep the state directory, backups and retained receipts private to the operator and service account. Avoid shared interactive IDs. UIDs are part of historical records: retire admissions before disabling an account, and prevent reassignment of its number while any retained register or snapshot uses it.

Use a local Linux filesystem supporting SQLite locking, atomic no-replace rename, and file and directory fsync. Use trusted parent paths without symlinks. Keep the installed environment and unit under administrator control. Select the host, named on-call owner, eligible data, recovery-point objective (maximum acceptable loss since backup), restoration time objective, alert destination and retention period before admitting real work. Evidence fields are short references or text; put confidential source documents in their existing access-controlled store. A short initial pilot with the team's own change decisions fits this profile. Do not submit secrets, school or medical records, or data requiring individual erasure: this schema retains immutable history for the life of a register.

## Install the exact candidate

The change-review candidate workflow retains the checkout SHA, wheel and source distribution, package verification, UID and systemd acceptance receipts, and a checksum inventory. Use the bundle from a successful run on the intended revision. In the extracted artifact root, run `sha256sum -c change-review-evidence/SHA256SUMS`. Confirm that `source-commit.txt` names the reviewed revision and read both acceptance outcomes. The inventory checks bytes against the retained build; it is not an external publisher signature.

On an approved host, install the exact retained wheel into a fresh root-owned Python environment at `/opt/commonwealth`. Substitute actual account names and the local artifact path in the examples. A fresh wheel install uses the standard library for the running service.

```sh
python3 -m venv /opt/commonwealth
/opt/commonwealth/bin/python -m pip install --no-index --no-deps /path/to/unfinished_commonwealth-0.1.4rc3-py3-none-any.whl
/opt/commonwealth/bin/commonwealth-change-review --help
```

Install the packaged unit and provision a private register once. The Python command locates the resources in the installed distribution. The environment file must contain the two numeric UIDs, not the account names. Add users to the socket group using your host's usual identity-management process, and start fresh login sessions to pick up the group changes.

```sh
deploy_dir=$(/opt/commonwealth/bin/python -c 'from importlib.resources import files; print(files("commonwealth.change_review_v1").joinpath("deploy"))')
install -d -m 0755 /etc/commonwealth
install -m 0644 "$deploy_dir/commonwealth-change-review.service" /etc/systemd/system/commonwealth-change-review.service
install -m 0600 "$deploy_dir/change-review.env.example" /etc/commonwealth/change-review.env
# Edit the installed private env file and set SUBMITTER_UID and REVIEWER_UID.
install -d -o commonwealth-review -g commonwealth-review -m 0700 /var/lib/commonwealth-change-review
sudo -u commonwealth-review /opt/commonwealth/bin/commonwealth-change-review init /var/lib/commonwealth-change-review/reviews.sqlite
systemctl daemon-reload
systemctl start commonwealth-change-review.service
```

Retain the resulting register ID outside the service database. A second init refuses the existing database. After a reboot test and acceptance, the operator may enable startup with `systemctl enable commonwealth-change-review.service`. Multiple admitted accounts can be configured with repeated UID arguments in an operator-reviewed unit override. Apply membership changes by restarting the service. The unit has no public listener or RPC that administers users.

## Record a change and its review

Run client commands from their assigned OS accounts. From either one:

```sh
/opt/commonwealth/bin/commonwealth-change-review ready --socket /run/commonwealth-change-review/service.sock
/opt/commonwealth/bin/commonwealth-change-review request --socket /run/commonwealth-change-review/service.sock --input request.json
```

Use standard input in place of `--input` when appropriate. Keep local request/response files private. Replace `REGISTER_ID` below with the retained ID verified through `ready`. A candidate change in this project, for example, could cite a paired study comparing a revised handoff with the direct policy:

```json
{"op":"submit","register_id":"REGISTER_ID","id":"handoff-review-001","title":"Review adoption of the checked handoff","proposal":"Assess whether the extra inspection cost is justified for the initial workload.","evidence":["Unfinished Commonwealth PR 20, prospective successor draw, 24 workshops"]}
```

The reviewer pages through proposals with `{"op":"list","after":0,"limit":20}` and uses each returned `next_after` until it is null. Read the exact proposal with `{"op":"get","id":"handoff-review-001","owner_uid":1001}` using its actual owner UID. Compare its evidence before submitting a decision. Replace both placeholders and the example UID:

```json
{"op":"decide","register_id":"REGISTER_ID","id":"handoff-review-001","owner_uid":1001,"submission_digest":"SUBMISSION_DIGEST","decision":"decline","rationale":"The direct policy achieved the same correctness and used fewer primary inspections in the cited trial."}
```

These example texts do not record an actual project decision. Submitting accounts can retrieve their own record by ID. Proposal IDs are scoped by owner UID, a decision binds the specific submitted content, and a former submitter cannot decide their own proposal following a role change. Reuse the original payload after a lost acknowledgement; then read back the result. A different proposal or decision using the same identity returns a conflict. A new register requires a new explicit selection. A receipt records the reviewer’s decision, not completion of downstream work.

## Monitor the service

Run `ready` from an admitted account and monitor the unit’s ActiveState and restart count. A successful probe checks local admission and database access. Each register supports 10,000 proposals and a 128 MiB database ceiling. The socket accepts bounded 64 KiB packets and at most 32 pending clients (four per UID). Saturation or a disconnected client can make the outcome of a write uncertain. Retain original intents and retry those exact requests. The record count, resource bounds and hosted latency samples do not establish a production SLO on another machine.

Use `check` as the service account against a retained snapshot and its successful backup receipt. It verifies both databases, compares register identities and the snapshot digest, and reports pending reviews, capacity, backup age and disk headroom. Choose thresholds to match the approved backup schedule and volume. The following example checks a one-day recovery point and 512 MiB of free space:

```sh
commonwealth-change-review check /var/lib/commonwealth-change-review/reviews.sqlite /private/backups/shift-001.sqlite /private/backups/shift-001.json --max-backup-age-seconds 86400 --min-free-bytes 536870912
```

Schedule the check with the host’s monitoring system and route a nonzero exit to the named operator. `check` exits 2 when an observed threshold fails and 1 when verification cannot complete. The operator’s retained timestamp supplies backup age. The check confirms register identity and counts; it cannot detect all divergent copies with the same identity. Use a single active writer and periodically run a timed restore. Protect client output and administrative shell histories; the service journal should contain process lifecycle information and content-free error labels.

## Back up, restore and rotate

1. Schedule a brief outage. Stop the service, confirm that it is inactive and fence any other copy. As the service account, back up the source to a fresh name in a private directory and retain the command's JSON output in a new private receipt file. Verify a successful exit before using the receipt. Both source and destination use a cooperative lifetime lock during copying. Do not remove lock files to clear contention.
2. Copy the protected snapshot and its receipt to the approved off-host recovery destination. Retain the digest independently of the file. Periodically retrieve that actual copy for a restore drill. `backup` leaves the current database intact. Restart after the backup when appropriate.
3. Restore only from a closed standalone snapshot. Supply its retained SHA-256. The restore command creates a fresh destination, verifies register identity and recorded decisions, and reports the resulting digest. Compare counts, digest, UID mappings, outstanding work and the last accepted receipt. A restore preserves the same register ID; review any work committed since the snapshot before accepting traffic.
4. To cut over, stop and fence the old unit. Preserve the old state directory and all of its contents together, including SQLite sidecars if present. Provision a new owner-only state directory at the standard service path. Run restore into its previously absent `reviews.sqlite`, verify it, then start exactly one service. If history or UID mapping is uncertain, keep it stopped. For a binary rollback, use a previously verified, schema-compatible wheel and retain a backup of the current state before switching.
5. For scheduled retention, close admissions, drain outstanding reviews, inventory client receipts and every backup, and archive the entire closed register according to the approved policy. Initialize a fresh register for a new retention period and distribute its new identity. Record the expiry or destruction of the closed register and its copies through the organization’s retention procedure. There is no automatic per-row deletion.

```sh
# Run as service owner, in protected locations; use new filenames.
umask 077
(set -C; commonwealth-change-review backup /var/lib/commonwealth-change-review/reviews.sqlite /private/backups/shift-001.sqlite > /private/backups/shift-001.json)
commonwealth-change-review restore /private/backups/shift-001.sqlite /private/drills/recovered.sqlite --expected-sha256 RETAINED_SHA256
commonwealth-change-review verify /private/drills/recovered.sqlite
```

A directory-sync failure after publication can leave a complete file at its intended name. For `published_durability_unconfirmed` or an init `publication_unconfirmed`, inspect the named private file, verify the record count and digest, and investigate the storage device before any cutover. For disk exhaustion, stop new admissions, preserve confirmed records, free space using the host procedure, verify the database, and retry original requests. Use only a new destination name for a new recovery attempt. No command silently overwrites a retained register.

## Launch decision

The hosted jobs exercise a disposable deployment and retain their receipts. A live launch additionally needs the operator’s target-host record: exact artifact and UID assignments, authorized workload, retention period, observed workload/latency, oldest acceptable backup, actual restore time, verified off-host copy, and the person receiving alerts and accepting rollback responsibility. Complete at least one submission and decision from the assigned accounts, simulate a lost acknowledgement with an exact retry, exercise restart and recovery, and record the observations before admitting normal traffic. The first live go/no-go belongs to the named host owner.

References: [Linux Unix-domain sockets](https://man7.org/linux/man-pages/man7/unix.7.html), [systemd execution environment](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html), [SQLite online backup](https://sqlite.org/backup.html).
