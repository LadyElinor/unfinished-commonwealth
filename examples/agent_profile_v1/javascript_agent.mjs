// Independent example decision process. Reads a brief on stdin and echoes its opaque ID.
import { readFileSync } from "node:fs";
const brief = JSON.parse(readFileSync(0, "utf8"));
const profile = "unfinished-commonwealth.agent-participation.v1";
if (brief.profile !== profile || brief.external_authority !== "NONE") {
  throw new Error("Unsupported brief");
}
const result = { profile, brief_id: brief.brief_id };
if (brief.role === "assembly-researcher") {
  if (brief.choices.includes("offer")) {
    Object.assign(result, {choice: "offer", terms: "Review the named draft and disclose limits."});
  } else if (brief.choices.includes("deliver")) {
    const fiscal = brief.source_draft.fiscal;
    Object.assign(result, {choice: "deliver", report: "The draft states its fiscal effect as: " + fiscal,
      sources: "Submitted draft SHA-256 " + brief.draft_digest,
      limits: "Text inspection alone cannot verify expenses or whether a right was infringed."});
  } else {
    Object.assign(result, {choice: "decline", reason: "No open offer or award for this actor."});
  }
} else if (brief.role === "workshop-proposer") {
  const work = brief.work;
  if (work.halted || work.successor_observation_required || brief.attempts_remaining === 0 ||
      !Object.hasOwn(work.methods, "quality-stream")) {
    Object.assign(result, {choice: "decline", reason: "The offered task lacks a usable method or observation."});
  } else {
    Object.assign(result, {choice: "propose", method: "quality-stream",
      prediction: {primary_correct: 0.8, peer_on_time: 0.7},
      purpose: "Use the declared quality flags in one pass to leave inspection capacity for the neighboring job."});
  }
} else {
  throw new Error("Unknown participation role");
}
process.stdout.write(JSON.stringify(result) + "\n");
