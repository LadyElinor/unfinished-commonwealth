"""Standalone deterministic JSON policy. No host, client, fixture or evaluator imports."""
import json
import sys

METHOD = {"valid-reading-mean-v1": "quality-stream", "scheduled-slot-yield-v1": "zero-fill"}


def decide(brief):
    base = {"profile": brief["profile"], "brief_id": brief["brief_id"]}
    if brief["role"] == "study-proposer" and brief["profile"] == "unfinished-commonwealth.study-decision.v1":
        contract = brief["work"]["contract"]
        if contract is None:
            return dict(base, choice="request-evidence", reason="Read the current task order.")
        if contract not in METHOD:
            return dict(base, choice="decline", reason="Unsupported contract.")
        return dict(base, choice="propose", method=METHOD[contract])
    if brief["role"] != "workshop-proposer" or brief["profile"] not in (
            "unfinished-commonwealth.agent-participation.v1", "unfinished-commonwealth.agent-participation.v1.1"):
        raise ValueError("unsupported role or profile")
    work = brief["work"]
    if work["halted"] or work["successor_observation_required"] or not brief["attempts_remaining"]:
        return dict(base, choice="decline", reason="No current observation or usable task.")
    if "quality-stream" not in work["methods"]:
        return dict(base, choice="decline", reason="No supported method.")
    return dict(base, choice="propose", method="quality-stream",
                prediction={"primary_correct": 0.75, "peer_on_time": 0.75},
                purpose="Inspect validity flags once and preserve peer capacity.")


if __name__ == "__main__":
    print(json.dumps(decide(json.load(sys.stdin))))
