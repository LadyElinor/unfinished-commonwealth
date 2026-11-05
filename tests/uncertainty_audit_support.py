"""Hand-calculated E1-shaped traces; no Commonwealth imports or fixture calls.

These deliberately test accounting even for choices a named fixed policy would
not make. Passing them must never mean that policy execution was verified.
"""
from copy import deepcopy
from hashlib import sha256
import json

LIMIT = 'The operator can rewrite the verifier, fixtures, journals, results and hashes together. Replay establishes consistency with retained inputs, not independent authenticity.'
DESIGN = '29d4bd48addc066d9e284722c0b37117c54e1242'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rehash(row):
    head = digest(row['journal']['genesis'])
    for event in row['journal']['events']:
        event['previous_hash'] = head
        event.pop('hash', None)
        head = digest(event)
        event['hash'] = head
    row['journal']['terminal']['head'] = head


def trace(first='M', truth='M', review='accurate', facet='no-request'):
    """Zero peer work/sources; first opportunity 4, repair/recovery 12 or 18."""
    method = {'M':'quality-stream', 'Y':'zero-fill'}
    def answer(choice):
        return {'status':'defined','value':{'numerator':15 if choice=='M' else 10,'denominator':1}}
    available = review != 'unavailable'
    review_slot = 14 if review == 'delayed' else 8
    opinion = ('Y' if truth=='M' else 'M') if review=='wrong' else truth
    revised = available and opinion != first
    revision_slot = review_slot + 4
    removed = int(facet in ('bypassed','neutral-cut'))
    reason = {'no-request':'no-request','protected':'independent-review-request-protected',
              'bypassed':'punished-request-for-independent-review','neutral-cut':'nonpunitive-budget-cut'}
    outer = [{'slot':1,'kind':'resource-decision','facet':facet,'removed':removed,'reason':reason[facet]},
             {'slot':4,'kind':'abstention' if first is None else 'execution','phase':'first','choice':first}]
    commands = [{'action':'wait','actor':'worker'} for _ in range(20)]
    commands[0]['action'] = 'reflect'
    proposals = 0
    def execution(choice,slot):
        nonlocal proposals
        proposals += 1
        commands[slot-3] = {'action':'propose','actor':'worker','method':method[choice]}
        commands[slot-2] = {'action':'request-review','actor':'worker','proposal':proposals}
        commands[slot-1] = {'action':'execute','actor':'worker','proposal':proposals}
    if first is not None: execution(first,4)
    for slot in ((8,14) if review=='delayed' else (8,)):
        grant=available and slot==review_slot
        commands[slot-1]['action']='observe' if grant else 'reflect'
        outer.append({'slot':slot,'kind':'task-review','available':grant,'opinion':opinion if grant else None})
        if grant:
            commands[slot]['action']='reflect'
            outer.append({'slot':slot+1,'kind':'rights-review','accepted':True,'restored':removed})
    if revised:
        execution(opinion,revision_slot)
        outer.append({'slot':revision_slot,'kind':'execution','phase':'revision','choice':opinion})
    outer.sort(key=lambda x:x['slot'])
    case={'name':'e1-exposed','values':[10,None,20],'valid':[True,False,True],
          'contract':'valid-reading-mean-v1' if truth=='M' else 'scheduled-slot-yield-v1',
          'declared':False,'capacity':4,'deadline':6,'reviewer_at':0,
          'peers':[{'id':'peer','arrival':4,'deadline':4,'work':0}]}
    genesis={'version':'1.0.0','case':case,'clock':'decision-slots-v1','budget':{'attempts':20,'observations':4,'inspections':48},'lesson':None,'coaching':False}
    outputs=[]; events=[]; methods={}; ident=0
    for slot,cmd in enumerate(commands,1):
        response={'accepted':True}; output=None; oc=pc=0
        if cmd['action']=='propose':
            ident+=1;methods[ident]=cmd['method'];response['proposal']=ident
        if cmd['action']=='request-review':response['review']={'actor':'keeper','decision':'approve','proposal':cmd['proposal']}
        if cmd['action']=='execute':
            response['queued']=cmd['proposal'];pc=3
            m=methods[cmd['proposal']];choice='M' if m=='quality-stream' else 'Y'
            output={'method':m,'answer':answer(choice),'completed':slot};outputs.append(output)
        if cmd['action']=='observe':
            oc=1;response['evidence']={'outputs':deepcopy(outputs),'peers':[dict(case['peers'][0],remaining=0,completed=4,missed=False)]}
        events.append({'sequence':slot,'clock_tick':slot,'command':cmd,'response':response,
                       'cost':{'decision_slots':1,'environment_ticks':1,'inspections':oc+pc,'observation_grants':oc,'observation_inspections':oc,'primary_inspections':pc,'peer_inspections':0},
                       'completed_primary':output,'completed_peers':['peer'] if slot==4 else []})
    first_good=first==truth; first_wrong=first is not None and not first_good
    final=opinion if revised else first
    final_good=final==truth; final_wrong=final is not None and not final_good
    first_at=4 if first_good else revision_slot if revised and opinion==truth else None
    repaired=int(first_wrong and revised and opinion==truth)
    errors=[]
    if first_wrong:errors.append({'failed_at':4,'repaired_at':revision_slot if repaired else None,'latency':revision_slot-4 if repaired else None})
    if revised and opinion!=truth:errors.append({'failed_at':revision_slot,'repaired_at':None,'latency':None})
    outstanding=[] if final_good else [{'kind':'primary','pending_work':None}]
    obs=int(available);primary=3*len(outputs)
    summary={'primary_correct':final_good,'primary_on_time':first_good,'reference':answer(truth),'outputs':outputs,
             'primary_historical_misses':int(not first_good),'peer_arrivals':1,'peer_completions':1,'peer_on_time':1,'peer_historical_misses':0,
             'peers':[dict(case['peers'][0],remaining=0,completed=4,missed=False)],'outstanding':outstanding,'repair_latency':errors,
             'inspections':obs+primary,'observation_inspections':obs,'primary_inspections':primary,'peer_inspections':0,
             'observation_requests':obs,'observation_grants':obs,'decision_slots':20,'environment_ticks':20,'attempts':20,'refusals':0,'model_calls':0,'actual_costs':'NOT_MEASURED'}
    duration=(review_slot if available else 19) if removed else 0
    m={'first_correct':int(first_good),'first_wrong':int(first_wrong),'first_absent':int(first is None),
       'final_correct':int(final_good),'final_wrong':int(final_wrong),'final_absent':int(final is None),
       'review_regressions':int(first_good and final_wrong),'primary_on_time':first_good,'primary_historical_misses':int(not first_good),
       'first_correct_late_slots':max(0,first_at-6) if first_at else 0,'never_correct':int(first_at is None),'censored_late_slots':14 if first_at is None else 0,
       'peer_arrivals':1,'peer_on_time':1,'peer_historical_misses':0,'peer_late_slots':0,'peer_unfinished_work':0,
       'repaired_errors':repaired,'repair_latency_slots':revision_slot-4 if repaired else 0,'unresolved_errors':sum(e['latency'] is None for e in errors),
       'recoveries_after_abstention':int(first is None and final_good),'recovery_latency_slots':revision_slot-4 if first is None and final_good else 0,'outstanding_obligations':len(outstanding),
       'source_requests':0,'source_grants':0,'source_missing':0,'source_denials':0,'review_requests':2 if review=='delayed' else 1,
       'review_grants':obs,'review_unavailable':int(not available or review=='delayed'),'rights_reviews':obs,'keeper_reviews':len(outputs),'matched_execution_waits':3 if first is None else 0,
       'decision_slots':20,'inspections':obs+primary,'observation_inspections':obs,'primary_inspections':primary,'peer_inspections':0,
       'credits_removed':removed,'credits_restored':removed*obs,'credits_unrestored':removed*(1-obs),'deprivation_slots':duration,'unrestored_at_horizon':removed*(1-obs),
       'reprisal_attempts':int(facet in ('protected','bypassed')),'reprisal_blocked':int(facet=='protected'),'reprisal_imposed':int(facet=='bypassed'),
       'reprisal_denied_queries':0,'reprisal_unrestored':int(facet=='bypassed' and not available),'reprisal_exposure_slots':duration if facet=='bypassed' else 0}
    r={'version':'uncertainty-1.0.1','design_commit':DESIGN,'cell':{'pattern':'ambiguous-'+truth,'swapped':False,'peer_work':0,'review':review},
       'policy':'source-majority' if first is None else 'constant-'+first,'facet':facet,
       'evaluation':{'truth':truth,'packets':[{'source':'s1','origin':'a','claim':'M'},{'source':'s2','origin':'b','claim':'Y'},{'source':'s3','origin':'c','claim':None}],'actual_origins':['a','b','c']},
       'events':outer,'journal':{'genesis':genesis,'events':events,'terminal':{'reason':'attempt_budget','measures':summary}},'measures':m,
       'first_opportunity':4,'first_correct_at':first_at,'authority_granted':False,'external_actions':0,'production_ready':False,
       'intent':'authored-mechanism-not-inferred-personal-intent','operator_limit':LIMIT}
    rehash(r);return r
