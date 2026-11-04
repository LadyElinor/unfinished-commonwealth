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
  assert.equal(c.values.length, c.valid.length);
  assert(['quality-stream', 'zero-fill', 'positive-only'].includes(method));
  let total = 0n, count = 0n;
  c.values.forEach((v, i) => {
    assert(v === null || Number.isSafeInteger(v));
    assert.equal(typeof c.valid[i], 'boolean');
    assert(!(c.valid[i] && v === null));
    if (method === 'zero-fill' || (method === 'quality-stream' ? c.valid[i] : v !== null && v > 0)) {
      total += BigInt(v ?? 0); count++;
    }
  });
  return ratio(total, count);
}

function verifyStudy(dir) {
  const files = readdirSync(dir).filter(f => f.endsWith('.json')).sort();
  assert(files.length > 0);
  let outputs = 0;
  for (const file of files) {
    const j = read(join(dir, file)), c = j.genesis.case, m = j.terminal.measures;
    assert(['valid-reading-mean-v1', 'scheduled-slot-yield-v1'].includes(c.contract));
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
    outputs += completed.length;
  }
  return {journals:files.length, completed_outputs:outputs, operator_limit:limit};
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

const [mode,path] = process.argv.slice(2);
assert(path && ['study','assembly'].includes(mode), 'Usage: node audit_measurement.mjs study JOURNAL_DIR | assembly PUBLIC_RECORD');
console.log(JSON.stringify(mode === 'study' ? verifyStudy(path) : recount(path), null, 2));
