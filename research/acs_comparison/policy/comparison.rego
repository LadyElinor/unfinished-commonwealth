package commonwealth
import rego.v1

# The trusted fixture adapter supplies the context below. Only the local
# sample operation is in this experiment's allowlist.
args := input.policy_target.value
tool := input.snapshot.tool_call.name
actor := input.snapshot.envelope.agent.id

default verdict := {"decision": "deny", "reason": "invalid_context"}

verdict := {"decision": "deny", "reason": "outside_operation_scope"} if {
    tool != "simulate"
} else := {"decision": "deny", "reason": "unmandated_actor"} if {
    actor != args.executor
} else := {"decision": "deny", "reason": "no_operator_intent"} if {
    args.origin != "operator"
} else := {"decision": "deny", "reason": "missing_evidence"} if {
    count(args.evidence) == 0
} else := {"decision": "allow", "reason": "scoped_fixture"} if {
    actor == args.executor
    tool == "simulate"
    args.origin == "operator"
    args.resource == args.target
    args.receipt.kind == "AUTHORIZATION"
    args.receipt.result == "PASS"
    args.receipt.scope == "SYNTHETIC_SCRATCH_ONLY"
    args.receipt.case_id == args.mandate.case_id
    args.receipt.actor == args.mandate.authorizer
    args.receipt.policy_digest == args.mandate.policy_digest
    args.receipt.proposal_digest == args.mandate.proposal_digest
    args.mandate.max_uses == 1
    args.tick <= args.mandate.expires_tick
    count(args.evidence) == 1
    args.evidence[0].id == args.required_source
    crypto.sha256(args.evidence[0].content) == args.evidence[0].content_digest
}
