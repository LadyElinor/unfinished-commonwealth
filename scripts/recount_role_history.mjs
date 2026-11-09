// Recount the exposed R2 fixture outcomes from actor, file and clock receipts.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import { gunzipSync } from 'node:zlib';

const data = readFileSync(process.argv[2] || 0);
const decoded = data[0] === 0x1f && data[1] === 0x8b ? gunzipSync(data) : data;
const input = decoded.toString('utf8').trimEnd().split(/\r?\n/);
const worlds = new Map([
  ['direct-approver', 'voter'], ['moved-approver', 'voter'], ['material-witness', 'briefer'],
  ['nonvoting-selector', 'selector'], ['financial-dependence', 'voter'],
  ['mistaken-identity', null], ['former-colleague', null], ['minor-connection', null], ['disputed-allegation', null]
]);
const keys = new Set();
const groups = {};
for (const line of input) {
  const {world, reserve_available: reserve, trace: t, score: s} = JSON.parse(line);
  assert(worlds.has(world) && [true, false].includes(reserve) && [4, 5].includes(t.budget));
  assert.equal(t.version, 'role-history-rehearsal-1');
  assert(['office', 'history'].includes(t.arm));
  const group = [t.arm, reserve, t.budget].join('/');
  assert(!keys.has(world + '/' + group), 'duplicate matrix cell');
  keys.add(world + '/' + group);
  const g = groups[group] ??= {episodes:0, voted:0, no_reserve:0, exhausted:0, conflicts_retained:0,
    eligible_removed:0, missed:0, unsupported_corrections:0, unsupported_misconduct:0,
    slots:0, completed_ticks:[], late_payments:0, claimant_demands:0, claimant_work:0};
  const slot = worlds.get(world);
  const excluded = Object.values(t.initial_screen).filter(e => e.excluded).map(e => e.person);
  const retained = slot && t.authorized[slot] === 'P1' ? ['P1'] : [];
  const wrong = [...new Set(excluded.filter(id => id !== 'P1' || !slot))].sort();
  assert.deepEqual(s.conflicts_retained, retained);
  assert.deepEqual(s.eligible_removed, wrong);
  assert(t.events.length <= t.budget);
  assert.deepEqual(t.events.map(e => e.at), t.events.map((_, i) => 4+i));
  assert.deepEqual(t.timeline.map(x => x.tick), [3,4,5,6,7,8]);
  const last = t.timeline.at(-1), vote = t.events.find(e => e.action === 'vote');
  const roles = {select:'selector', brief:'briefer', vote:'voter'};
  for (const e of t.events.filter(e => e.action in roles)) assert.equal(e.actor, t.authorized[roles[e.action]]);
  assert.equal(t.terminal, vote ? 'voted' : Object.keys(t.authorized).length ? 'budget-exhausted' : 'no-eligible-reserve');
  const finalFindings = last.inquiry.findings;
  assert.deepEqual(finalFindings, vote?.findings ?? {});
  const owed = Object.entries(finalFindings).filter(([,v]) => v === 'correction-owed').map(([k]) => k);
  const missed = owed.includes('B') ? [] : ['B'];
  assert.deepEqual(s.missed_corrections, missed);
  assert.deepEqual(s.unsupported_corrections, owed.filter(k => k !== 'B').sort());
  assert.deepEqual(t.misconduct_findings, []);
  assert.equal(s.unsupported_misconduct, t.misconduct_findings.length);
  assert.equal(s.review_elapsed, vote ? vote.at-3 : null);
  assert.equal(s.reviewer_slots, t.events.length);
  assert.equal(s.owner, last.inquiry.next_owner);
  for (const snap of t.timeline) {
    assert.equal(snap.payment.supported_credit_units, snap.tick < 5 ? 0 : 100);
    assert.equal(snap.participation.choices['further-contact'], 'declined');
    const effort = snap.participation.recorded_burden.institution.recorded_units;
    assert.equal(effort, t.events.filter(e => e.at <= snap.tick).length + Number(snap.tick >= 5));
  }
  const firstCredit = t.timeline.find(x => x.payment.supported_credit_units === 100).tick;
  assert.equal(s.payment_tick, firstCredit);
  assert.equal(s.lateness, Math.max(0, firstCredit - 5));
  assert.equal(s.claimant_demands, last.participation.required_person_work_records.length);
  assert.equal(s.claimant_work, last.participation.recorded_burden['affected-person'].recorded_units);
  g.episodes++;
  if (vote) { g.voted++; g.completed_ticks.push(vote.at - 3); }
  else if (t.terminal === 'budget-exhausted') g.exhausted++;
  else g.no_reserve++;
  g.conflicts_retained += retained.length;
  g.eligible_removed += wrong.length;
  g.missed += missed.length;
  g.unsupported_corrections += s.unsupported_corrections.length;
  g.unsupported_misconduct += t.misconduct_findings.length;
  g.slots += t.events.length;
  g.late_payments += Number(s.lateness > 0);
  g.claimant_demands += s.claimant_demands;
  g.claimant_work += s.claimant_work;
}
assert.equal(keys.size, 72, 'matrix coverage');
const hash = createHash('sha256').update(input.join('\n') + '\n').digest('hex');
console.log(JSON.stringify({episodes:keys.size, normalized_stream_sha256:hash, groups}, null, 2));
