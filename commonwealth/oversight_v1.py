"""Read-only, protocol-2 decision evidence for an operator. See docs/OVERSIGHT_TRACE.md."""
import argparse
import json
import sqlite3
import sys

from .engine import digest
from .store import Workshop

PROFILE = "commonwealth.proposal-oversight.v1"


def trace(workshop, through_seq=None):
    # Read and replay in a single transaction via the original workshop API.
    events = workshop.events()
    through = len(events) - 1 if through_seq is None else through_seq
    if type(through) is not int or not 0 <= through < len(events):
        raise ValueError("cutoff must name an existing event")
    prefix = events[:through + 1]
    if any(e.get("protocol") != 2 for e in prefix):
        raise ValueError("only protocol-2 prefixes are supported")
    proposals, testimonies = {}, {}
    scenario = prefix[0]["command"]["scenario"]
    generation = 1
    for event in prefix[1:]:
        command, result, seq = event["command"], event["result"], event["seq"]
        action, actor = command["action"], command["actor"]
        mark = {"seq": seq, "actor": actor}
        if action == "handoff":
            generation += 1
            scenario = command["scenario"]
        elif action == "propose":
            proposals[result["id"]] = {
                "proposal_id": result["id"], "generation": generation, "scenario": scenario,
                "method": command["method"], "proposal": mark,
                "approval": None, "execution": None, "observation": None,
            }
        elif action in ("approve", "execute"):
            proposals[command["proposal"]]["approval" if action == "approve" else "execution"] = mark
        elif action == "observe":
            obs = result["observation"]
            if "prediction_proposal" in obs:
                proposals[obs["prediction_proposal"]]["observation"] = {
                    **mark, "id": result["id"], "tick": obs["tick"],
                    "peer_on_time": obs["new_peer_on_time"], "primary_correct": obs["primary_correct"],
                }
        elif action == "testify":
            testimonies[result["id"]] = {
                **mark, "id": result["id"], "about": command["observation"], "acknowledgments": [],
            }
        elif action == "listen":
            testimonies[command["testimony"]]["acknowledgments"].append(mark)
    return {"profile": PROFILE, "source_family": "one-local-workshop-journal",
            "through_seq": through, "prefix_head": digest(prefix[-1]),
            "episodes": list(proposals.values()), "accounts": list(testimonies.values()),
            "intent": "not-established", "authority_granted": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", help="an existing local workshop database")
    parser.add_argument("--through-seq", type=int, help="last included journal sequence (inclusive)")
    args = parser.parse_args(argv)
    try:
        packet = trace(Workshop(args.database), args.through_seq)
    except (OSError, ValueError, sqlite3.Error) as err:
        print(json.dumps({"status": "REFUSED", "reason": str(err)}), file=sys.stderr)
        return 2
    print(json.dumps(packet, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
