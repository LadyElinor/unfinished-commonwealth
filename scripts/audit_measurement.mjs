// Independent arithmetic and roll-call audit. No Python imports, signatures or authentication.
import {readFileSync, readdirSync} from 'node:fs';
import {join} from 'node:path';
import assert from 'node:assert/strict';

const read = file => JSON.parse(readFileSync(file, 'utf8'));
const limit = 'The operator can rewrite the inputs and checker. Signatures, custody and historical authenticity are outside this numerical audit.';

function ratio(total, denominator) {
  if (denominator === 0n) return {status:'undefined', value:null};
  let a = total < 0n ? -total : total, b = denominator;
  while (b !== 0n) [a, b] = [b, a % b];
  const n = Number(total / a), d = Number(denominator / a);
  assert(Number.isSafeInteger(n) && Number.isSafeInteger(d));
  return {status:'defined', value:{numerator:n, denominator:d}};
}

// Definition directly from the task order, separate from candidate method execution.
function reference(c) {
  const validMean = c.contract === 'valid-reading-mean-v1';
  const terms = c.values.filter((v,i) => validMean ? c.valid[i] : v !== null);
  const numerator = terms.reduce((sum,v) => sum + BigInt(v), 0n);
  return ratio(numerator, BigInt(validMean ? terms.length : c.values.length));
}

function answer(c, method) {
  assert(['quality-stream', 'zero-fill', 'positive-only'].includes(method));
  let total = 0n, count = 0n;
  c.values.forEach((v, i) => {
    if (method === 'zero-fill' || (method === 'quality-stream' ? c.valid[i] : v !== null && v > 0)) {
      total += BigInt(v ?? 0); count++;
    }
  });
  return ratio(total, count);
}

function natural(value) {
  assert(Number.isSafeInteger(value) && value >= 0, 'expected a nonnegative safe integer');
  return value;
}

function validateCase(c) {
  assert(Array.isArray(c.values) && Array.isArray(c.valid));
  assert.equal(c.values.length, c.valid.length);
  assert(['valid-reading-mean-v1', 'scheduled-slot-yield-v1'].includes(c.contract));
  c.values.forEach((v, i) => {
    assert(v === null || Number.isSafeInteger(v));
    assert.equal(typeof c.valid[i], 'boolean');
    assert(!(c.valid[i] && v === null));
  });
  natural(c.capacity); natural(c.deadline);
}

// Reconstruct FIFO service from the shared capacity and the recorded non-peer spend.
function auditPeers(j) {
  const c = j.genesis.case, m = j.terminal.measures;
  const peers = c.peers.map(p => {
    natural(p.arrival); natural(p.deadline); natural(p.work);
    assert(typeof p.id === 'string' && p.id.length && p.deadline >= p.arrival);
    return {...p, remaining:p.work, completed:null, missed:false};
  }).sort((a,b) => a.arrival - b.arrival || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  assert.equal(new Set(peers.map(p => p.id)).size, peers.length);
  assert(['decision-slots-v1','observation-clock-v1'].includes(j.genesis.clock));
  const limit = natural(j.genesis.budget.inspections);
  let tick = 0, spent = 0, peerSpend = 0;
  for (const e of j.events) {
    const advances = j.genesis.clock === 'decision-slots-v1' ||
      ['observe','inspect','request-evidence'].includes(e.command.action);
    if (advances) tick++;
    assert.equal(e.cost.decision_slots, 1);
    assert.equal(e.clock_tick, tick);
    assert.equal(e.cost.environment_ticks, Number(advances));
    const prior = natural(e.cost.observation_inspections) + natural(e.cost.primary_inspections);
    const available = advances ? Math.min(c.capacity, limit - spent) : 0;
    assert(prior <= available);
    let free = available - prior;
    const closed = [];
    if (advances) {
      // A zero-work arrival completes immediately, even with no capacity.
      for (const p of peers) {
        if (p.arrival === tick && p.remaining === 0) { p.completed = tick; closed.push(p.id); }
      }
      for (const p of peers) {
        if (p.completed !== null || p.arrival > tick) continue;
        const used = Math.min(p.remaining, free);
        free -= used; p.remaining -= used;
        if (p.remaining === 0) { p.completed = tick; closed.push(p.id); }
        else if (tick >= p.deadline) p.missed = true;
      }
    }
    const service = available - prior - free;
    assert.equal(e.cost.peer_inspections, service);
    assert.equal(e.cost.inspections, prior + service);
    assert.deepEqual(e.completed_peers, closed);
    if (e.completed_primary !== null) {
      assert(advances);
      assert.equal(e.completed_primary.completed, tick);
    }
    spent += prior + service; peerSpend += service;
  }
  assert.equal(m.decision_slots, j.events.length);
  assert.deepEqual(m.peers, peers);
  assert.deepEqual(m.outstanding.filter(o => o.kind === 'peer'),
    peers.filter(p => p.completed === null).map(p => (
      {kind:'peer', id:p.id, remaining:p.remaining, arrived:p.arrival <= tick})));
  assert.equal(m.peer_arrivals, peers.filter(p => p.arrival <= tick).length);
  assert.equal(m.peer_completions, peers.filter(p => p.completed !== null).length);
  assert.equal(m.peer_on_time, peers.filter(p => p.completed !== null && !p.missed).length);
  assert.equal(m.peer_historical_misses, peers.filter(p => p.missed).length);
  assert.equal(m.peer_inspections, peerSpend); assert.equal(m.inspections, spent);
  assert.equal(m.environment_ticks, tick);
  return m.peer_historical_misses;
}

function matrixRows(path, files) {
  const matrix = read(path), rows = new Map();
  assert.equal(matrix.design_revision, 'D1');
  assert.equal(matrix.case_count, 12);
  assert.equal(matrix.arm_count, 18);
  assert.equal(matrix.runs.length, 2 * 12 * 18);
  assert.equal(new Set(matrix.runs.map(r => r.case)).size, 12);
  assert.equal(new Set(matrix.runs.map(r => r.arm)).size, 18);
  for (const r of matrix.runs) {
    assert(['decision-slots-v1','observation-clock-v1'].includes(r.clock));
    assert.equal(r.id, [r.clock,r.case,r.arm].join('--'));
    assert(!rows.has(r.id + '.json'), 'repeated matrix cell');
    rows.set(r.id + '.json', r);
  }
  assert.deepEqual(files, [...rows.keys()].sort(), 'directory differs from full D1 matrix');
  return rows;
}

function verifyStudy(dir, matrixPath) {
  const files = readdirSync(dir).filter(f => f.endsWith('.json')).sort();
  assert(files.length > 0);
  const rows = matrixPath ? matrixRows(matrixPath, files) : null;
  let outputs = 0, peerMisses = 0;
  for (const file of files) {
    const j = read(join(dir, file)), c = j.genesis.case, m = j.terminal.measures;
    if (rows) {
      const r = rows.get(file);
      assert.equal(c.name, r.case); assert.equal(j.genesis.clock, r.clock);
      assert.equal(r.replay.head, j.terminal.head);
      assert.deepEqual(r.budget, j.genesis.budget); assert.deepEqual(r.measures, m);
    }
    validateCase(c);
    peerMisses += auditPeers(j);
    const expected = reference(c);
    assert.deepEqual(m.reference, expected, file);
    const completed = j.events.map(e => e.completed_primary).filter(Boolean);
    assert.deepEqual(m.outputs, completed, file);
    const correct = completed.map(out => {
      assert.deepEqual(out.answer, answer(c, out.method), file);
      const a = out.answer.value, b = expected.value;
      return a === null || b === null ? a === b : a.numerator === b.numerator && a.denominator === b.denominator;
    });
    assert.equal(m.primary_correct, correct.at(-1) ?? false, file);
    assert.equal(m.primary_on_time, correct.some((v,i) => v && completed[i].completed <= c.deadline), file);
    assert.equal(m.primary_historical_misses,
      Number(m.environment_ticks > 0 && m.environment_ticks >= c.deadline && !m.primary_on_time), file);
    const repairs = [];
    completed.forEach((out,i) => {
      if (correct[i]) return;
      const next = completed.find((_,k) => k > i && correct[k]);
      repairs.push({failed_at:out.completed, repaired_at:next?.completed ?? null,
        latency:next ? next.completed - out.completed : null});
    });
    assert.deepEqual(m.repair_latency, repairs, file);
    outputs += completed.length;
  }
  return {journals:files.length, completed_outputs:outputs, verified_peer_misses:peerMisses, full_matrix_checked:rows !== null, operator_limit:limit};
}

function recount(path) {
  const r = read(path), seats = r.registry.people, rounds = [];
  let current, kind, day = 0;
  for (const {body} of r.entries) {
    const {type, args} = body.command;
    if (type === 'file' || type === 'revise') kind = args.document.kind;
    if (type === 'open' || (type === 'executive' && args.decision === 'veto')) {
      assert(!current); current = {ref:args.ref, round:type === 'open' ? 1 : 2, kind, votes:new Map()};
    } else if (type === 'vote') {
      assert(current && current.ref === args.ref && current.round === args.round);
      assert(['commons','duration'].includes(seats[body.actor].role) && !current.votes.has(body.actor));
      assert(['yes','no','abstain'].includes(args.choice)); current.votes.set(body.actor,args.choice);
    } else if (type === 'tick') {
      if (current && args.day >= current.closes) {
        const chambers = {};
        for (const chamber of ['commons','duration']) {
          const voters = Object.keys(seats).filter(k => seats[k].role === chamber);
          const cast = voters.filter(k => current.votes.has(k)).map(k => current.votes.get(k));
          const [yes,no,abstain] = ['yes','no','abstain'].map(v => cast.filter(x => x === v).length);
          const quorum = cast.length * 2 > voters.length;
          const supermajority = current.round === 2 || current.kind === 'amendment';
          chambers[chamber] = {seats:voters.length,present:cast.length,yes,no,abstain,quorum,
            passed:quorum && (supermajority ? 3 * yes >= 2 * voters.length : yes > no)};
        }
        rounds.push({ref:current.ref,round:current.round,chambers}); current = null;
      }
      day = args.day;
    }
    if (current && current.closes === undefined) current.closes = day + 2;
  }
  return {closed_rounds:rounds, operator_limit:limit};
}

const [mode,path,matrixPath,...extra] = process.argv.slice(2);
assert(path && extra.length === 0 && (mode === 'study' || (mode === 'assembly' && !matrixPath)),
  'Usage: node audit_measurement.mjs study JOURNAL_DIR [D1_RESULTS] | assembly PUBLIC_RECORD');
console.log(JSON.stringify(mode === 'study' ? verifyStudy(path,matrixPath) : recount(path), null, 2));
