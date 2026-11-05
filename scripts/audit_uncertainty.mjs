// Independent trace arithmetic/accounting, not host authentication or policy replay.
// Uses no Python code and no candidate aggregator; only Node standard libraries.
import {CHECKER_VERSION, DESIGN, LIMIT, check, same, keys, integer, digest, parseJSON, lines, readSummary, rowSchema} from './audit_uncertainty_input.mjs';
import {createHash} from 'node:crypto';

const [input, summaryPath] = process.argv.slice(2);
check(process.argv.length===4,'usage: node audit_uncertainty.mjs ROWS SUMMARY|--partial');
const gcd = (a,b) => b === 0n ? a : gcd(b,a % b);
function answer(values, flags, method) {
  const selected = method === 'quality-stream' ? values.filter((v,i)=>flags[i]) : values.filter(v=>v!==null);
  const n = method === 'quality-stream' ? selected.length : values.length;
  if (!n) return {status:'undefined',value:null};
  const total=selected.reduce((a,v)=>a+BigInt(v),0n), d=BigInt(n), g=gcd(total<0n?-total:total,d);
  return {status:'defined',value:{numerator:Number(total/g),denominator:Number(d/g)}};
}

function choreography(r){
  const plan=Array.from({length:20},()=>({action:'wait',actor:'worker'}));
  const used=new Set();
  const put=(slot,action,fields={})=>{check(integer(slot)&&slot>=1&&slot<=20&&!used.has(slot),'overlapping phase');used.add(slot);plan[slot-1]={action,actor:'worker',...fields};};
  let previous=0,first=null,revision=null;
  const sources=[],reviews=[],rights=[];
  for(const e of r.events){
    check(integer(e.slot)&&e.slot>previous&&e.slot<=20,'outer event order');previous=e.slot;
    if(e.kind==='resource-decision')keys(e,['slot','kind','facet','removed','reason'],'resource event');
    else if(e.kind==='source'){keys(e,['slot','kind','request','granted','packet'],'source event');check(typeof e.granted==='boolean'&&integer(e.request),'source event types');sources.push(e);}
    else if(e.kind==='task-review'){keys(e,['slot','kind','available','opinion'],'review event');check(typeof e.available==='boolean'&&['M','Y',null].includes(e.opinion),'review event types');reviews.push(e);}
    else if(e.kind==='rights-review'){keys(e,['slot','kind','accepted','restored'],'rights event');check(e.accepted===true&&integer(e.restored),'rights event types');rights.push(e);}
    else if(['execution','abstention'].includes(e.kind)){
      keys(e,['slot','kind','phase','choice'],'output phase');
      check(e.kind==='execution'?['M','Y'].includes(e.choice):e.choice===null,'output choice');
      check(['first','revision'].includes(e.phase),'output phase domain');
      if(e.phase==='first'){check(first===null,'duplicate first phase');first=e;}
      else {check(revision===null&&e.kind==='execution','duplicate/absent revision');revision=e;}
    }else throw Error('unknown outer event');
  }
  const reason={'no-request':'no-request',protected:'independent-review-request-protected',bypassed:'punished-request-for-independent-review','neutral-cut':'nonpunitive-budget-cut'};
  same(r.events[0],{slot:1,kind:'resource-decision',facet:r.facet,removed:Number(['bypassed','neutral-cut'].includes(r.facet)),reason:reason[r.facet]},'resource reason');
  check(r.events.filter(e=>e.kind==='resource-decision').length===1,'duplicate resource event');
  put(1,'reflect');
  check([0,2,3].includes(sources.length),'source attempt count');
  sources.forEach((e,i)=>{check(e.slot===i+2,'source slot');put(e.slot,e.granted?'observe':'reflect');});
  check(first!==null&&first.slot===sources.length+4,'initial phase boundary');
  let proposal=0;
  const phase=e=>{
    if(e.kind==='abstention'){for(let i=e.slot-2;i<=e.slot;i++)put(i,'wait');}
    else {proposal++;put(e.slot-2,'propose',{method:e.choice==='M'?'quality-stream':'zero-fill'});put(e.slot-1,'request-review',{proposal});put(e.slot,'execute',{proposal});}
  };
  phase(first);
  reviews.forEach(e=>put(e.slot,e.available?'observe':'reflect'));
  rights.forEach(e=>put(e.slot,'reflect'));
  if(revision){check(rights.length===1&&revision.slot===rights[0].slot+3,'revision boundary');phase(revision);}
  return plan;
}
function terminal(j,outputs,reference,good,s,head){
  const repairs=outputs.flatMap((o,i)=>{
    if(good[i])return [];
    const later=outputs.find((p,k)=>k>i&&good[k])?.completed??null;
    return [{failed_at:o.completed,repaired_at:later,latency:later===null?null:later-o.completed}];
  });
  const outstanding=good.length&&good.at(-1)?[]:[{kind:'primary',pending_work:null}];
  if(s.remaining)outstanding.push({kind:'peer',id:'peer',remaining:s.remaining,arrived:true});
  const onTime=outputs.some((o,i)=>good[i]&&o.completed<=6);
  same(j.terminal,{head,reason:'attempt_budget',measures:{primary_correct:Boolean(good.length&&good.at(-1)),primary_on_time:onTime,
    reference,outputs,primary_historical_misses:Number(s.primaryMissed),peer_arrivals:1,peer_completions:Number(s.peerDone!==null),
    peer_on_time:Number(s.peerDone!==null&&s.peerDone<=4),peer_historical_misses:Number(s.peerMissed),
    peers:[{...j.genesis.case.peers[0],remaining:s.remaining,completed:s.peerDone,missed:s.peerMissed}],outstanding,repair_latency:repairs,
    inspections:s.obs+s.primary+s.peerCost,observation_inspections:s.obs,primary_inspections:s.primary,peer_inspections:s.peerCost,
    observation_requests:s.obs,observation_grants:s.obs,decision_slots:20,environment_ticks:20,attempts:20,refusals:0,model_calls:0,actual_costs:'NOT_MEASURED'}},'terminal state');
}

const METRIC_GROUPS={"correctness":["first_correct","first_wrong","first_absent","final_correct","final_wrong","final_absent","review_regressions"],"cost":["source_requests","source_grants","source_missing","source_denials","review_requests","review_grants","review_unavailable","rights_reviews","keeper_reviews","matched_execution_waits","decision_slots","inspections","observation_inspections","primary_inspections","peer_inspections"],"delay":["primary_on_time","primary_historical_misses","first_correct_late_slots","never_correct","censored_late_slots"],"peer_harm":["peer_arrivals","peer_on_time","peer_historical_misses","peer_late_slots","peer_unfinished_work"],"repair":["repaired_errors","repair_latency_slots","unresolved_errors","recoveries_after_abstention","recovery_latency_slots","outstanding_obligations"],"resources":["credits_removed","credits_restored","credits_unrestored","deprivation_slots","unrestored_at_horizon"],"retaliation":["reprisal_attempts","reprisal_blocked","reprisal_imposed","reprisal_denied_queries","reprisal_unrestored","reprisal_exposure_slots"]};
const groups=[new Map(),new Map(),new Map()], seen=new Set(), hash=createHash('sha256');
let count=0;
for await (const line of lines(input,hash)) {
  check(count<3840,'too many rows');
  const r=parseJSON(line); rowSchema(r);
  const m=r.measures, j=r.journal, c=j.genesis.case, events=j.events;
  const reference=answer(c.values,c.valid,c.contract==='valid-reading-mean-v1'?'quality-stream':'zero-fill');
  const proposals=new Map(), outputs=[];
  let head=digest(j.genesis);
  const planned=choreography(r);
  let remaining=r.cell.peer_work, peerDone=null, peerMissed=false, primaryMissed=false, obs=0, primary=0, peerCost=0;
  for (let i=0;i<20;i++) {
    const e=events[i], tick=i+1, cmd=e.command;
    keys(e,['sequence','command','response','clock_tick','cost','completed_primary','completed_peers','previous_hash','hash'],'D1 event fields');
    check(e.previous_hash===head,'journal previous hash');
    const payload={...e};delete payload.hash;head=digest(payload);check(e.hash===head,'journal event hash');
    same(cmd,planned[i],'command/outer phase linkage');
    check(e.sequence===tick && e.clock_tick===tick,'slot order');
    check(e.cost.decision_slots===1 && e.cost.environment_ticks===1,'free deliberation');
    check(cmd.actor==='worker' && e.response.accepted===true,'unexpected D1 refusal');
    check(['observe','reflect','wait','propose','request-review','execute'].includes(cmd.action),'oracle or unsupported action');
    let capacity=4, oc=0, pc=0, wc=0, completed=null, completedPeers=[];
    if (tick===4 && remaining===0) {peerDone=tick; completedPeers.push('peer');}
    if (cmd.action==='observe') {
      same(e.response,{accepted:true,evidence:{outputs,peers:[{...c.peers[0],remaining,completed:peerDone,missed:peerMissed}]}},'observation receipt');
      oc=1; capacity--;
    }
    if(['reflect','wait'].includes(cmd.action))same(e.response,{accepted:true},'passive receipt');
    if (cmd.action==='propose') {
      check(['quality-stream','zero-fill'].includes(cmd.method),'method');
      const id=proposals.size+1;
      check([...proposals.values()].every(p=>p.executed),'unresolved prior proposal');
      same(e.response,{accepted:true,proposal:id},'proposal receipt');
      proposals.set(id,{method:cmd.method,approved:false,executed:false});
    }
    if (cmd.action==='request-review') {
      const p=proposals.get(cmd.proposal); check(p && !p.approved && !p.executed,'review state'); p.approved=true;
      same(e.response,{accepted:true,review:{actor:'keeper',decision:'approve',proposal:cmd.proposal}},'keeper receipt');
    }
    if (cmd.action==='execute') {
      const p=proposals.get(cmd.proposal); check(p?.approved && !p.executed,'keeper required'); p.executed=true;
      same(e.response,{accepted:true,queued:cmd.proposal},'execution receipt');
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
  const denied=source.filter(e=>!e.granted).length, firstOpportunity=source.length+4;
  const initial=outputs.filter(o=>o.completed<=firstOpportunity);
  check(initial.length<=1,'multiple initial outputs');
  const firstAbsent=Number(initial.length===0);
  const firstGood=Number(initial.length===1&&good[0]), firstWrong=Number(initial.length===1&&!good[0]);
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
  for(const [k,v] of Object.entries(expected)){
    check(k==='primary_on_time'?typeof m[k]==='boolean':integer(m[k]),`metric type ${k}`);
    check(Number(m[k])===v,`metric ${k}`);
  }
  check(firstGood+firstWrong+firstAbsent===1&&expected.final_correct+expected.final_wrong+expected.final_absent===1,'outcome partitions');
  terminal(j,outputs,reference,good,{remaining,peerDone,peerMissed,primaryMissed,obs,primary,peerCost},head);
  const identity=JSON.stringify([r.facet,r.policy,r.cell.pattern,r.cell.swapped,r.cell.peer_work,r.cell.review]);
  check(!seen.has(identity),'duplicate cell');seen.add(identity);
  [[r.facet,r.policy],[r.facet,r.policy,r.cell.review],[r.facet,r.policy,r.cell.pattern]].forEach((key,i)=>{
    const k=JSON.stringify(key), e=groups[i].get(k)??{key,cells:0,totals:Object.fromEntries(Object.keys(expected).map(k=>[k,0]))};
    e.cells++;for(const [metric,v] of Object.entries(expected))e.totals[metric]+=v;groups[i].set(k,e);
  });
  count++;
}
check(count>0,'empty stream');
const streamDigest=hash.digest('hex');
if(summaryPath!=='--partial'){
  const summary=readSummary(summaryPath);
  keys(summary,['version','design_commit','status','episode_count','episodes_sha256','all_records_replayed','metric_groups','totals','by_review','by_pattern','authority_granted','external_actions','model_calls','production_ready','actual_costs','holdout','operator_limit'],'summary fields');
  check(summary.version==='uncertainty-1.0.1'&&summary.design_commit===DESIGN&&summary.status==='EXPOSED_DETERMINISTIC_ONLY'&&summary.all_records_replayed===true&&summary.authority_granted===false&&summary.external_actions===0&&summary.model_calls===0&&summary.production_ready===false&&summary.actual_costs==='NOT_MEASURED'&&summary.holdout===false&&summary.operator_limit===LIMIT,'summary scope');
  same(summary.metric_groups,METRIC_GROUPS,'summary metric groups');
  check(count===3840 && summary.episode_count===count && summary.episodes_sha256===streamDigest,'matrix count/digest');
  for(const [i,name] of ['totals','by_review','by_pattern'].entries()){
    const sort=xs=>xs.sort((a,b)=>JSON.stringify(a.key).localeCompare(JSON.stringify(b.key)));
    same(sort([...groups[i].values()]),sort(summary[name]),`summary ${name}`);
  }
}
console.log(JSON.stringify({verified:true,checker_version:CHECKER_VERSION,complete_matrix:summaryPath!=='--partial',policy_verified:false,evidence_authenticated:false,episodes:count,episodes_sha256:streamDigest,scope:'INDEPENDENT_ARITHMETIC_AND_TRACE_ACCOUNTING_NOT_POLICY_REPLAY_OR_AUTHENTICITY',authority_granted:false}));
