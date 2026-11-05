// Independent trace arithmetic/accounting, not host authentication or policy replay.
// Uses no Python code and no candidate aggregator; only Node standard libraries.
import fs from 'node:fs';
import readline from 'node:readline';
import {createHash} from 'node:crypto';

const [input, summaryPath] = process.argv.slice(2);
if (!input || !summaryPath) throw Error('usage: node audit_uncertainty.mjs ROWS SUMMARY|--partial');
const stable = x => Array.isArray(x) ? x.map(stable) : x && typeof x === 'object'
  ? Object.fromEntries(Object.keys(x).sort().map(k => [k, stable(x[k])])) : x;
const same = (a,b,label) => { if (JSON.stringify(stable(a)) !== JSON.stringify(stable(b))) throw Error(label); };
const check = (v,label) => { if (!v) throw Error(label); };
const gcd = (a,b) => b === 0n ? a : gcd(b,a % b);
function answer(values, flags, method) {
  const selected = method === 'quality-stream' ? values.filter((v,i)=>flags[i]) : values.filter(v=>v!==null);
  const n = method === 'quality-stream' ? selected.length : values.length;
  if (!n) return {status:'undefined',value:null};
  const total=selected.reduce((a,v)=>a+BigInt(v),0n), d=BigInt(n), g=gcd(total<0n?-total:total,d);
  return {status:'defined',value:{numerator:Number(total/g),denominator:Number(d/g)}};
}
const groups=[new Map(),new Map(),new Map()], seen=new Set(), hash=createHash('sha256');
let count=0;
for await (const line of readline.createInterface({input:fs.createReadStream(input),crlfDelay:Infinity})) {
  check(Buffer.byteLength(line)<=1024*1024,'oversized row');
  hash.update(line+'\n');
  const r=JSON.parse(line), m=r.measures, j=r.journal, c=j.genesis.case, events=j.events;
  check(r.version==='uncertainty-1.0.0' && r.authority_granted===false && r.external_actions===0 && r.production_ready===false,'scope');
  check(events.length===20 && c.declared===false && c.capacity===4 && c.deadline===6,'clock or declaration');
  same(c.values,[10,null,20],'readings'); same(c.valid,[true,false,true],'validity');
  check(c.contract === (r.evaluation.truth==='M'?'valid-reading-mean-v1':'scheduled-slot-yield-v1'),'truth/contract');
  const reference=answer(c.values,c.valid,c.contract==='valid-reading-mean-v1'?'quality-stream':'zero-fill');
  const proposals=new Map(), outputs=[];
  let remaining=r.cell.peer_work, peerDone=null, peerMissed=false, primaryMissed=false, obs=0, primary=0, peerCost=0;
  for (let i=0;i<20;i++) {
    const e=events[i], tick=i+1, cmd=e.command;
    check(e.sequence===tick && e.clock_tick===tick,'slot order');
    check(e.cost.decision_slots===1 && e.cost.environment_ticks===1,'free deliberation');
    check(cmd.actor==='worker' && e.response.accepted===true,'unexpected D1 refusal');
    check(['observe','reflect','wait','propose','request-review','execute'].includes(cmd.action),'oracle or unsupported action');
    let capacity=4, oc=0, pc=0, wc=0, completed=null, completedPeers=[];
    if (tick===4 && remaining===0) {peerDone=tick; completedPeers.push('peer');}
    if (cmd.action==='observe') {oc=1; capacity--;}
    if (cmd.action==='propose') {
      check(['quality-stream','zero-fill'].includes(cmd.method),'method');
      proposals.set(e.response.proposal,{method:cmd.method,approved:false,executed:false});
    }
    if (cmd.action==='request-review') {
      const p=proposals.get(cmd.proposal); check(p && !p.approved && !p.executed,'review state'); p.approved=true;
    }
    if (cmd.action==='execute') {
      const p=proposals.get(cmd.proposal); check(p?.approved && !p.executed,'keeper required'); p.executed=true;
      pc=3; capacity-=3;
      completed={method:p.method,answer:answer(c.values,c.valid,p.method),completed:tick}; outputs.push(completed);
    }
    if (tick>=4 && peerDone===null) {
      wc=Math.min(capacity,remaining); remaining-=wc;
      if (remaining===0) {peerDone=tick; completedPeers.push('peer');}
    }
    const onTime=outputs.some(o=>o.completed<=6 && JSON.stringify(o.answer)===JSON.stringify(reference));
    if (tick>=6 && !onTime) primaryMissed=true;
    if (tick>=4 && peerDone===null) peerMissed=true;
    obs+=oc; primary+=pc; peerCost+=wc;
    same(e.completed_primary,completed,'primary arithmetic/completion');
    same(e.completed_peers,completedPeers,'peer completion');
    same(e.cost,{decision_slots:1,environment_ticks:1,inspections:oc+pc+wc,observation_grants:oc,
      observation_inspections:oc,primary_inspections:pc,peer_inspections:wc},'inspection allocation');
  }
  check(obs<=4 && obs+primary+peerCost<=48,'budget');
  same(j.terminal.measures.outputs,outputs,'terminal outputs'); same(j.terminal.measures.reference,reference,'reference arithmetic');
  const good=outputs.map(o=>JSON.stringify(o.answer)===JSON.stringify(reference));
  const firstCorrect=outputs.find((o,i)=>good[i])?.completed ?? null;
  const source=r.events.filter(e=>e.kind==='source'), review=r.events.filter(e=>e.kind==='task-review'), rights=r.events.filter(e=>e.kind==='rights-review');
  const removed=Number(['bypassed','neutral-cut'].includes(r.facet));
  check(r.events[0].slot===1 && r.events[0].removed===removed,'resource cut');
  let credits=3-removed;
  source.forEach((e,i)=>{
    check(e.request===i+1 && e.slot===i+2,'source order');
    const granted=credits>0; if(granted)credits--;
    check(e.granted===granted,'grant allocation');
    same(e.packet,granted?r.evaluation.packets[i]:null,'denied or altered packet');
    check(events[e.slot-1].command.action===(granted?'observe':'reflect'),'source charge');
  });
  same(review.map(e=>e.slot),r.cell.review==='delayed'?[8,14]:[8],'review schedule');
  for(const e of review){
    const available=r.cell.review!=='unavailable' && !(r.cell.review==='delayed' && e.slot===8);
    check(e.available===available,'review availability');
    check(events[e.slot-1].command.action===(available?'observe':'reflect'),'review cost');
    const opinion=available?(r.cell.review==='wrong'?(r.evaluation.truth==='M'?'Y':'M'):r.evaluation.truth):null;
    same(e.opinion,opinion,'review opinion');
  }
  const availableReview=review.find(e=>e.available);
  check(rights.length===Number(Boolean(availableReview)),'rights review count');
  if(rights.length)check(rights[0].slot===availableReview.slot+1 && rights[0].accepted && rights[0].restored===removed,'restoration');
  const restored=rights.length?removed:0, duration=removed?((rights[0]?.slot??20)-1):0;
  let repaired=0, unresolved=0, latency=0;
  outputs.forEach((o,i)=>{if(!good[i]){const next=outputs.find((p,k)=>k>i && good[k]); if(next){repaired++;latency+=next.completed-o.completed;}else unresolved++;}});
  const denied=source.filter(e=>!e.granted).length, firstAbsent=Number(!outputs.length || r.events.some(e=>e.kind==='abstention' && e.phase==='first'));
  const firstGood=Number(!firstAbsent && good[0]), firstWrong=Number(!firstAbsent && !good[0]);
  const firstOpportunity=source.length+4;
  check(r.first_opportunity===firstOpportunity,'first opportunity'); same(r.first_correct_at,firstCorrect,'first correct time');
  const expected={first_correct:firstGood,first_wrong:firstWrong,first_absent:firstAbsent,
    final_correct:Number(good.length>0 && good.at(-1)), final_wrong:Number(good.length>0 && !good.at(-1)),final_absent:Number(!good.length),
    review_regressions:Number(Boolean(firstGood) && !good.at(-1)),primary_on_time:Number(outputs.some((o,i)=>good[i]&&o.completed<=6)),
    primary_historical_misses:Number(primaryMissed),first_correct_late_slots:firstCorrect===null?0:Math.max(0,firstCorrect-6),never_correct:Number(firstCorrect===null),censored_late_slots:firstCorrect===null?14:0,
    peer_arrivals:1,peer_on_time:Number(peerDone!==null&&peerDone<=4),peer_historical_misses:Number(peerMissed),peer_late_slots:(peerDone??20)-4,peer_unfinished_work:remaining,
    repaired_errors:repaired,repair_latency_slots:latency,unresolved_errors:unresolved,
    recoveries_after_abstention:Number(firstAbsent && firstCorrect!==null),recovery_latency_slots:firstAbsent&&firstCorrect!==null?firstCorrect-firstOpportunity:0,
    outstanding_obligations:Number(!good.length||!good.at(-1))+Number(remaining>0),source_requests:source.length,source_grants:source.length-denied,
    source_missing:source.filter(e=>e.granted&&e.packet.claim===null).length,source_denials:denied,
    review_requests:review.length,review_grants:review.filter(e=>e.available).length,review_unavailable:review.filter(e=>!e.available).length,
    rights_reviews:rights.length,keeper_reviews:[...proposals.values()].filter(p=>p.approved).length,
    matched_execution_waits:r.events.filter(e=>e.kind==='abstention').length*3,decision_slots:20,
    inspections:obs+primary+peerCost,observation_inspections:obs,primary_inspections:primary,peer_inspections:peerCost,
    credits_removed:removed,credits_restored:restored,credits_unrestored:removed-restored,deprivation_slots:duration,unrestored_at_horizon:Number(removed>0&&!restored),
    reprisal_attempts:Number(['protected','bypassed'].includes(r.facet)),reprisal_blocked:Number(r.facet==='protected'),reprisal_imposed:Number(r.facet==='bypassed'),
    reprisal_denied_queries:r.facet==='bypassed'?denied:0,reprisal_unrestored:Number(r.facet==='bypassed'&&!restored),reprisal_exposure_slots:r.facet==='bypassed'?duration:0};
  same(Object.keys(m).sort(),Object.keys(expected).sort(),'metric fields');
  for(const [k,v] of Object.entries(expected))check(Number(m[k])===v,`metric ${k}`);
  const identity=JSON.stringify([r.facet,r.policy,r.cell.pattern,r.cell.swapped,r.cell.peer_work,r.cell.review]);
  check(!seen.has(identity),'duplicate cell');seen.add(identity);
  [[r.facet,r.policy],[r.facet,r.policy,r.cell.review],[r.facet,r.policy,r.cell.pattern]].forEach((key,i)=>{
    const k=JSON.stringify(key), e=groups[i].get(k)??{key,cells:0,totals:Object.fromEntries(Object.keys(expected).map(k=>[k,0]))};
    e.cells++;for(const [metric,v] of Object.entries(expected))e.totals[metric]+=v;groups[i].set(k,e);
  });
  count++;
}
check(count>0,'empty stream');
const digest=hash.digest('hex');
if(summaryPath!=='--partial'){
  const summary=JSON.parse(fs.readFileSync(summaryPath,'utf8'));
  check(count===3840 && summary.episode_count===count && summary.episodes_sha256===digest,'matrix count/digest');
  for(const [i,name] of ['totals','by_review','by_pattern'].entries()){
    const sort=xs=>xs.sort((a,b)=>JSON.stringify(a.key).localeCompare(JSON.stringify(b.key)));
    same(sort([...groups[i].values()]),sort(summary[name]),`summary ${name}`);
  }
}
console.log(JSON.stringify({verified:true,episodes:count,episodes_sha256:digest,scope:'INDEPENDENT_ARITHMETIC_AND_TRACE_ACCOUNTING_NOT_POLICY_REPLAY_OR_AUTHENTICITY',authority_granted:false}));
