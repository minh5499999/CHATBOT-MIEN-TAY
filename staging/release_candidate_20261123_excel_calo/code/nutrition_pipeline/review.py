"""Explicit local review actions. Empty production reviewer policy grants nobody approval."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from offline_nutrition.trust import require,read_json,iso_date
from .intake import sha,write_new

STATES={'MISSING_SOURCE','IMPORTED_UNVERIFIED','NEEDS_REVIEW','APPROVED','REJECTED','BLOCKED'}
def local(root,name):
    require(isinstance(name,str) and ':' not in name and not name.startswith(('/','\\')) and all(p not in ('','.','..') for p in name.replace('\\','/').split('/')),'INVALID_LOCAL_PATH','Expected relative bundle path')
    p=(Path(root)/name).resolve();require(p.is_relative_to(Path(root).resolve()) and p.is_file(),'LOCAL_FILE_MISSING','Local subject/evidence missing');return p

class ReviewQueue:
    def __init__(self,root):self.root=Path(root).resolve()
    def events(self):
        previous=None;events=[]
        for index,p in enumerate(sorted((self.root/'review_events').glob('*.json')),1):
            require(p.name==f'{index:06d}.json','REVIEW_CHAIN_INVALID','Missing/renamed event')
            event=read_json(p.read_bytes())
            require(event.get('previous_sha256')==previous and event.get('sequence')==index,'REVIEW_CHAIN_INVALID','Review history changed')
            previous=sha(p);events.append(event)
        return events
    def record(self,decision):
        # A caller must submit an explicit action. Reading metadata/importing never calls this.
        require(isinstance(decision,dict),'REVIEW_SCHEMA','Decision object required')
        action=decision.get('action');require(action in STATES,'REVIEW_SCHEMA','Unknown review state')
        actor=decision.get('actor');require(isinstance(actor,str) and actor.strip(),'REVIEW_ACTOR_REQUIRED','Explicit actor required')
        require(isinstance(decision.get('reason'),str) and decision['reason'].strip(),'REVIEW_REASON_REQUIRED','Explain the review action')
        scopes=decision.get('review_scope');require(isinstance(scopes,list) and scopes and all(isinstance(x,str) for x in scopes),'REVIEW_SCOPE_REQUIRED','Review scopes required')
        subject=local(self.root,decision.get('subject_path'));require(sha(subject)==decision.get('subject_sha256'),'SUBJECT_CHANGED','Review binds exact subject bytes')
        policy=read_json((self.root/'reviewer_policy.json').read_bytes())
        if action=='APPROVED':
            if 'source_text' in scopes:require(isinstance(decision.get('document_version'),str) and decision['document_version'].strip(),'MISSING_EVIDENCE','Evidence subject version required')
            granted=policy.get('reviewers',{}).get(actor,[])
            require(set(scopes)<=set(granted),'REVIEWER_NOT_AUTHORIZED','User-appointed reviewer must have every scope')
            checks=decision.get('evidence_checks')
            require(isinstance(checks,list) and bool(checks),'MISSING_EVIDENCE','Approval requires explicit source checks')
            for check in checks:
                require(isinstance(check,dict),'MISSING_EVIDENCE','Evidence check must be object')
                source=local(self.root,check.get('path'));require(sha(source)==check.get('sha256'),'EVIDENCE_DIGEST_MISMATCH','Evidence bytes changed')
                require(isinstance(check.get('document_version'),str) and check['document_version'].strip(),'MISSING_EVIDENCE','Evidence document version required')
                iso_date(check.get('collected_at'),'evidence.collected_at')
                passage=check.get('passage');require(isinstance(passage,str) and passage.strip() and passage in source.read_text(encoding='utf-8-sig'),'PASSAGE_NOT_FOUND','Approval must identify source passage')
        events=self.events();previous=sha(self.root/'review_events'/f'{len(events):06d}.json') if events else None
        event={**decision,'sequence':len(events)+1,'previous_sha256':previous,'recorded_at':datetime.now(timezone.utc).isoformat(),'policy_sha256':sha(self.root/'reviewer_policy.json'),'policy_scope':policy['scope']}
        (self.root/'review_events').mkdir(exist_ok=True)
        write_new(self.root/'review_events'/f'{len(events)+1:06d}.json',event)
        return event
    def approved(self,name,scopes,*,parse_json=True):
        p=local(self.root,name);events=[e for e in self.events() if e.get('subject_path')==name]
        require(bool(events),'INPUT_NOT_APPROVED','No explicit review action')
        event=events[-1];policy=read_json((self.root/'reviewer_policy.json').read_bytes())
        require(event.get('action')=='APPROVED' and event.get('subject_sha256')==sha(p),'INPUT_NOT_APPROVED','Latest decision is not approval for these bytes')
        require(event.get('policy_sha256')==sha(self.root/'reviewer_policy.json'),'REVIEW_POLICY_CHANGED','Review policy changed; review again')
        require(set(scopes)<=set(event['review_scope']) and set(scopes)<=set(policy.get('reviewers',{}).get(event['actor'],[])),'INSUFFICIENT_REVIEW_SCOPE','Missing authorized review scope')
        # Revalidate evidence at consumption time too.
        for check in event.get('evidence_checks',[]):require(sha(local(self.root,check['path']))==check['sha256'],'EVIDENCE_DIGEST_MISMATCH','Review evidence changed')
        return read_json(p.read_bytes()) if parse_json else p.read_bytes(),event
