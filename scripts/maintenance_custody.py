"""Prepare a paired maintenance manifest or recount it against separately held checkpoints."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile

from . import analyze_maintenance_pairs as study


# The counter is the zero-based index in the witnessed intake order.
DOMAIN = b"unfinished-commonwealth/maintenance-assignment/v1\x00"
PRE_INTAKE_PINS = ("agent", "environment", "reviewer_pool", "plain", "governed")


def checked_packet(raw, expected, name):
    study.require(sha256(raw).hexdigest() == expected, f"{name} checkpoint mismatch")
    return study.read_packet(raw)


def code_pins():
    paths = {"protocol_sha256": study.PROTOCOL, "analyzer_sha256": Path(study.__file__),
             "assignment_tool_sha256": Path(__file__)}
    return {key: sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}


def plain_first_positions(count, seed, roster_digest):
    prefix = DOMAIN + bytes.fromhex(seed) + bytes.fromhex(roster_digest)
    priorities = [sha256(prefix + i.to_bytes(4, "big")).digest() for i in range(count)]
    study.require(len(set(priorities)) == count, "assignment digest collision")
    ordered = sorted(range(count), key=priorities.__getitem__)
    return set(ordered[:count // 2])


def prepare(freeze_raw, roster_raw, freeze_digest, roster_digest, seed):
    freeze = checked_packet(freeze_raw, freeze_digest, "freeze")
    roster = checked_packet(roster_raw, roster_digest, "roster")
    study.fields(freeze, ("schema", "kind", "protocol_sha256", "analyzer_sha256", "assignment_tool_sha256",
                          "custody_plan_sha256", "grading_procedure_sha256", "pins"), "freeze")
    study.require(freeze["schema"] == "maintenance-custody-freeze-v1", "unsupported freeze")
    for field, observed in code_pins().items():
        study.require(freeze[field] == observed, f"frozen file mismatch: {field}")
    for field in ("custody_plan_sha256", "grading_procedure_sha256"):
        study.require(study.digest(freeze[field]), f"invalid {field}")
    study.fields(freeze["pins"], PRE_INTAKE_PINS, "pre-intake pins")
    study.fields(roster, ("schema", "freeze_sha256", "rubric_sha256", "tasks"), "roster")
    study.require(roster["schema"] == "maintenance-custody-roster-v1", "unsupported roster")
    study.require(roster["freeze_sha256"] == freeze_digest, "roster belongs to a different freeze")
    study.require(study.digest(seed), "expected a 32-byte witness seed in lowercase hex")
    tasks = roster["tasks"]
    study.require(isinstance(tasks, list) and len(tasks) in (4, 24), "expected a complete ordered roster")
    for task in tasks:
        study.fields(task, ("id", "lineage", "packet_sha256"), "roster task")

    plain_first = plain_first_positions(len(tasks), seed, roster_digest)
    manifest = {"schema": "maintenance-pairs-manifest-v1", "kind": freeze["kind"],
                "protocol_sha256": freeze["protocol_sha256"], "pins": {**freeze["pins"], "rubric": roster["rubric_sha256"]},
                "tasks": [dict(task, first_arm="plain" if i in plain_first else "governed") for i, task in enumerate(tasks)]}
    study.validate_manifest(manifest)
    return (json.dumps(manifest, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("ascii")


def check_blind_grades(mapping, grades, manifest_digest, outcomes):
    study.fields(mapping, ("schema", "manifest_sha256", "entries"), "blinding map")
    study.fields(grades, ("schema", "entries"), "blinded grades")
    study.require(mapping["schema"] == "maintenance-blinding-map-v1" and
                  mapping["manifest_sha256"] == manifest_digest, "wrong blinding map")
    study.require(grades["schema"] == "maintenance-blinded-grades-v1", "wrong blinded grade schema")
    study.require(isinstance(mapping["entries"], list) and isinstance(grades["entries"], list), "expected grade entry lists")
    # The ordinary analyzer has already validated the same outcome bytes.
    candidates = {(row["task"], row["arm"], number): candidate for row in outcomes["runs"]
                  for number, candidate in enumerate(row["candidates"], start=1)}
    by_id = {}
    for entry in grades["entries"]:
        study.fields(entry, ("blind_id", "patch_sha256", "grade"), "blind grade")
        blind = entry["blind_id"]
        study.require(study.digest(blind) and blind not in by_id, "invalid or duplicate blind grade ID")
        study.require(study.digest(entry["patch_sha256"]) and entry["grade"] in study.GRADES, "invalid blind grade")
        by_id[blind] = entry
    for entry in mapping["entries"]:
        study.fields(entry, ("task", "arm", "submission", "blind_id", "patch_sha256"), "mapping entry")
        blind = entry["blind_id"]
        study.require(study.digest(blind) and blind in by_id, "missing or reused blind grade")
        study.require(study.label(entry["task"]) and entry["arm"] in study.ARMS and
                      type(entry["submission"]) is int and entry["submission"] >= 1, "invalid submission address")
        slot = (entry["task"], entry["arm"], entry["submission"])
        study.require(slot in candidates, "unknown or duplicate mapped submission")
        candidate, grade = candidates.pop(slot), by_id.pop(blind)
        study.require(entry["patch_sha256"] == candidate["sha256"] == grade["patch_sha256"], "patch digest differs at grade join")
        study.require(candidate["grade"] == grade["grade"], "export disagrees with locked blind grade")
    study.require(not candidates and not by_id, "incomplete mapping or unused blind grades")


def publish_manifest(path, raw):
    # Publish complete bytes without replacing a prior checkpoint, including on concurrent retries.
    staging = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    temporary = Path(staging.name)
    try:
        with staging:
            staging.write(raw)
        try:
            os.link(temporary, path)
        except FileExistsError:
            study.require(path.read_bytes() == raw, "different manifest already exists at output path")
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("freeze", type=Path)
    shared.add_argument("roster", type=Path)
    shared.add_argument("manifest", type=Path)
    shared.add_argument("--freeze-sha256", required=True, help="witnessed before intake")
    shared.add_argument("--roster-sha256", required=True, help="witnessed before the seed draw")
    shared.add_argument("--seed", required=True, help="single 32-byte draw from the external witness, in hex")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("code-pins", help="print raw file digests for the pre-intake checkpoint")
    commands.add_parser("assign", parents=[shared], help="prepare the manifest before the first session")
    recount = commands.add_parser("recount", parents=[shared], help="verify the assignment and both subsequent locks")
    recount.add_argument("outcomes", type=Path)
    recount.add_argument("blinding_map", type=Path)
    recount.add_argument("grades", type=Path)
    recount.add_argument("--map-sha256", required=True, help="witnessed before blinded grading")
    recount.add_argument("--grades-sha256", required=True, help="grading lead's checkpoint before unblinding")
    recount.add_argument("--manifest-sha256", required=True, help="witnessed before either arm ran")
    recount.add_argument("--outcomes-sha256", required=True, help="witnessed final export after the locked grades and costs were joined")
    args = parser.parse_args(argv)
    try:
        if args.command == "code-pins":
            print(json.dumps(code_pins(), indent=2))
            return
        expected = prepare(args.freeze.read_bytes(), args.roster.read_bytes(), args.freeze_sha256, args.roster_sha256, args.seed)
        if args.command == "assign":
            publish_manifest(args.manifest, expected)
            print(sha256(expected).hexdigest())
            return
        manifest = args.manifest.read_bytes()
        study.require(manifest == expected, "manifest differs from replayed assignment")
        outcome_raw = args.outcomes.read_bytes()
        report = study.analyze(manifest, outcome_raw, args.manifest_sha256, args.outcomes_sha256)
        mapping = checked_packet(args.blinding_map.read_bytes(), args.map_sha256, "blinding map")
        grades = checked_packet(args.grades.read_bytes(), args.grades_sha256, "blind grades")
        check_blind_grades(mapping, grades, args.manifest_sha256, study.read_packet(outcome_raw))
        report["blind_grade_replay"] = {"matched_submissions": len(grades["entries"]), "map_sha256": args.map_sha256,
                                       "grades_sha256": args.grades_sha256}
        report["assignment_replay"] = {"algorithm": "maintenance-assignment-v1", "freeze_sha256": args.freeze_sha256,
                                       "roster_sha256": args.roster_sha256, "seed": args.seed,
                                       "custody_authentication": "external_review_required"}
        json.dump(report, sys.stdout, indent=2, allow_nan=False)
        print()
    except (ValueError, OSError) as error:
        parser.exit(2, f"Invalid custody handoff: {error}\n")


if __name__ == "__main__":
    main()
