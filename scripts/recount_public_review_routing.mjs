// Hand-counted reference paths for the frozen public rehearsal. Read JSON on stdin.
import fs from 'node:fs';
import {check, keys, parseJSON, same} from './audit_uncertainty_input.mjs';

const candidate = 'cab907ba2477802edfe846599c9155990127ef1221fbf27720a2ebebe41049be';
const source = 'be0a8ba8024e284a5727defa9e25624467f6398f85d8c5be343ed7dbdd16b8f2';
const consult = ['host', 'consult', 'validation'];
const paths = {
  fixed: [['fixed-selector', 'route', 'validation'], consult],
  direct: [['fixture-router', 'route', 'validation'], consult],
  abstain: [['fixture-router', 'route', 'abstained']],
  failure: [['fixture-router', 'route', 'failed-before-dispatch'], ['host', 'fallback', 'validation'], consult],
};

function recount(record) {
  keys(record, ['schema', 'source_sha256', 'brief', 'slot_budget_per_arm', 'runs'], 'header');
  const budgetControl = record.schema === 'public-review-routing-budget-v1';
  if (!budgetControl) same(record.schema, 'public-review-routing-v1', 'schema');
  same(record.source_sha256, source, 'source');
  const budget = record.slot_budget_per_arm;
  if (budgetControl) check(Number.isInteger(budget) && budget >= 0 && budget <= 3, 'budget');
  else same(budget, 3, 'budget');
  same(record.brief, {case: 'demo-2', candidate, eligible: ['validation', 'reporting']}, 'brief');
  check(Array.isArray(record.runs), 'runs');
  same(record.runs.map(run => run.arm).sort(), Object.keys(paths).sort(), 'arm roster');
  const summary = [];
  for (const run of record.runs) {
    const fields = ['arm', 'events', 'reviewer', 'selected_by', 'reviewed_candidate',
               'illustrative_grade', 'slots_used'];
    if (budgetControl) fields.push('blocked_action');
    keys(run, fields, 'run fields');
    const fullPath = paths[run.arm];
    const path = fullPath.slice(0, budget);
    const blocked = fullPath[budget]?.[1] ?? null;
    if (budgetControl) same(run.blocked_action, blocked, 'blocked action');
    check(Array.isArray(run.events) && run.events.length === path.length, 'event count');
    let slots = 0;
    for (const [i, [actor, action, result]] of path.entries()) {
      same(run.events[i], {actor, action, result, slots: 1}, run.arm + ' event ' + i);
      slots += run.events[i].slots;
    }
    same(run.slots_used, slots, 'spent slots');
    const consulted = path.at(-1)?.[1] === 'consult';
    const selection = path.find(([, action, result]) => action !== 'consult' && result === 'validation');
    const selectedBy = selection?.[0] ?? null;
    same(run.selected_by, selectedBy, 'selection authority');
    same(run.reviewer, selection ? 'validation' : null, 'reviewer');
    same(run.reviewed_candidate, consulted ? candidate : null, 'reviewed candidate');
    same(run.illustrative_grade, consulted ? 'correct' : null, 'illustrative grade');
    const row = {arm: run.arm, selected_by: selectedBy, consultations: Number(consulted), slots};
    if (budgetControl) row.blocked_action = blocked;
    summary.push(row);
  }
  return summary;
}

try {
  console.log(JSON.stringify(recount(parseJSON(fs.readFileSync(0, 'utf8'))), null, 2));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
