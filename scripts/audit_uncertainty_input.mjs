// Bounded JSON inputs for the E1 accounting checker. No Python dependencies.
import fs from 'node:fs';
import {createHash} from 'node:crypto';

export const CHECKER_VERSION='e1-accounting-1.1.0';
export const DESIGN='29d4bd48addc066d9e284722c0b37117c54e1242';
export const POLICIES=['constant-M','constant-Y','source-majority','origin-majority','corroborate-or-abstain'];
export const FACETS=['no-request','protected','bypassed','neutral-cut'];
export const PATTERNS=['agreement','lone-error','disclosed-copy','concealed-copy','sparse','silent','ambiguous-M','ambiguous-Y'];
export const REVIEWS=['accurate','delayed','wrong','unavailable'];
export const LIMIT='The operator can rewrite the verifier, fixtures, journals, results and hashes together. Replay establishes consistency with retained inputs, not independent authenticity.';
export const stable=x=>Array.isArray(x)?x.map(stable):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])):x;
export const check=(v,label)=>{if(!v)throw Error(label);};
export const same=(a,b,label)=>check(JSON.stringify(stable(a))===JSON.stringify(stable(b)),label);
export const keys=(x,names,label)=>{check(x!==null&&typeof x==='object'&&!Array.isArray(x),label);same(Object.keys(x).sort(),[...names].sort(),label);};
export const integer=x=>typeof x==='number'&&Number.isSafeInteger(x)&&x>=0&&!Object.is(x,-0);
export const canonical=x=>JSON.stringify(stable(x)).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
export const digest=x=>createHash('sha256').update(canonical(x)).digest('hex');

// JSON.parse alone silently discards duplicate names. Decode names before checking
// duplicates, including escaped spellings. E1's wire numbers are safe integers.
export function parseJSON(text){
  let i=0;
  const ws=()=>{while(/[ \t\r\n]/.test(text[i]??'!'))i++;};
  function string(){
    const start=i++;let escaped=false;
    while(i<text.length){const c=text[i++];if(c==='"'&&!escaped)return JSON.parse(text.slice(start,i));if(c==='\\'&&!escaped)escaped=true;else escaped=false;}
    throw Error('unterminated JSON string');
  }
  function value(depth){
    check(depth<=64,'JSON nesting limit');ws();const c=text[i];
    if(c==='"')return string();
    if(c==='{'||c==='['){
      const object=c==='{',end=object?'}':']',out=object?Object.create(null):[],seen=new Set();i++;ws();
      if(text[i]===end){i++;return out;}
      while(true){
        ws();let name;
        if(object){check(text[i]==='"','object name');name=string();check(!seen.has(name),'duplicate JSON name');seen.add(name);ws();check(text[i++]===':','object colon');}
        const v=value(depth+1);if(object)out[name]=v;else out.push(v);
        ws();if(text[i]===end){i++;return out;}check(text[i++ ]===',','JSON delimiter');
      }
    }
    for(const [literal,v] of [['true',true],['false',false],['null',null]])if(text.startsWith(literal,i)){i+=literal.length;return v;}
    const token=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(i));check(token,'JSON value');i+=token[0].length;
    const n=Number(token[0]);check(Number.isSafeInteger(n)&&!Object.is(n,-0),'unsafe JSON integer');return n;
  }
  const result=value(0);ws();check(i===text.length,'trailing JSON data');return result;
}
const decode=buffer=>new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(buffer);
export async function* lines(path,hasher){
  let pending=Buffer.alloc(0);
  for await(const chunk of fs.createReadStream(path,{highWaterMark:65536})){
    hasher.update(chunk);const data=Buffer.concat([pending,chunk]);let start=0,pos;
    while((pos=data.indexOf(10,start))!==-1){check(pos-start<=1024*1024,'oversized row');yield decode(data.subarray(start,pos));start=pos+1;}
    pending=Buffer.from(data.subarray(start));check(pending.length<=1024*1024,'oversized row');
  }
  check(pending.length===0,'JSONL final newline required');
}
export function readSummary(path){check(fs.statSync(path).size<=2*1024*1024,'oversized summary');return parseJSON(decode(fs.readFileSync(path)));}
export function rowSchema(r){
  keys(r,['authority_granted','cell','design_commit','evaluation','events','external_actions','facet','first_correct_at','first_opportunity','intent','journal','measures','operator_limit','policy','production_ready','version'],'row fields');
  check(r.version==='uncertainty-1.0.1'&&r.design_commit===DESIGN&&r.authority_granted===false&&r.production_ready===false&&r.external_actions===0&&r.operator_limit===LIMIT&&r.intent==='authored-mechanism-not-inferred-personal-intent','row scope');
  check(POLICIES.includes(r.policy)&&FACETS.includes(r.facet),'policy/facet domain');
  keys(r.cell,['pattern','swapped','peer_work','review'],'cell fields');
  check(PATTERNS.includes(r.cell.pattern)&&typeof r.cell.swapped==='boolean'&&[0,4,8].includes(r.cell.peer_work)&&REVIEWS.includes(r.cell.review),'cell domain');
  check(integer(r.first_opportunity)&&(r.first_correct_at===null||integer(r.first_correct_at)),'output times');
  keys(r.evaluation,['truth','packets','actual_origins'],'evaluation fields');
  check(['M','Y'].includes(r.evaluation.truth),'truth domain');
  check(Array.isArray(r.evaluation.packets)&&r.evaluation.packets.length===3,'packet count');
  r.evaluation.packets.forEach((p,i)=>{keys(p,['source','origin','claim'],'packet fields');check(p.source===`s${i+1}`&&['a','b','c'].includes(p.origin)&&['M','Y',null].includes(p.claim),'packet domain');});
  check(Array.isArray(r.evaluation.actual_origins)&&r.evaluation.actual_origins.length===3&&r.evaluation.actual_origins.every(x=>['a','b','c'].includes(x)),'origin declarations');
  keys(r.journal,['genesis','events','terminal'],'journal fields');
  const c={name:'e1-exposed',values:[10,null,20],valid:[true,false,true],contract:r.evaluation.truth==='M'?'valid-reading-mean-v1':'scheduled-slot-yield-v1',declared:false,capacity:4,deadline:6,reviewer_at:0,peers:[{id:'peer',arrival:4,deadline:4,work:r.cell.peer_work}]};
  same(r.journal.genesis,{version:'1.0.0',case:c,clock:'decision-slots-v1',budget:{attempts:20,observations:4,inspections:48},lesson:null,coaching:false},'genesis schedule/budget');
  check(Array.isArray(r.journal.events)&&r.journal.events.length===20&&Array.isArray(r.events)&&r.events.length<=9,'event bounds');
}
