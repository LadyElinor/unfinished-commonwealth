"""Recount closed public roll calls directly from the signed commands in an export."""
from .rules_v02 import CHAMBERS, require


def recount(bundle, state):
    casts={}
    for env in bundle["entries"]:
        actor=env["body"]["actor"]
        cmd=env["body"]["command"]
        if cmd["type"]=="vote":
            vote=cmd["args"]
            row=casts.setdefault((vote["ref"],vote["round"]),{})
            require(actor not in row,"recount found duplicate seat")
            row[actor]=vote["choice"]
    checked=[]
    for b in state.archive+([state.bill] if state.bill else []):
        for idx,tally in b["tallies"].items():
            votes=casts.get((b["ref"],int(idx)),{})
            require(votes==tally["roll_call"],"published roll call mismatch")
            for chamber in CHAMBERS:
                members=[k for k,s in bundle["registry"]["people"].items() if s["role"]==chamber]
                present=[votes[k] for k in members if k in votes]
                yes,no,abstain=[present.count(v) for v in ("yes","no","abstain")]
                quorum=len(present)>=len(members)//2+1
                passed=quorum and (yes >= (yes+no)//2+1 if idx=="1" and b["document"]["kind"]!="amendment" else yes >= (2*len(members)+2)//3)
                expected=dict(seats=len(members),present=len(present),yes=yes,no=no,abstain=abstain,quorum=quorum,passed=passed)
                require(expected==tally["chambers"][chamber],"independent tally disagrees")
            checked.append(dict(revision=b["version"],round=int(idx),chambers=tally["chambers"]))
    return checked
