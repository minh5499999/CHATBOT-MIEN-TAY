"""Bind production registry entries to explicit reviewed local actions, not names alone."""
from pathlib import Path
from offline_nutrition.trust import TrustStore,require,digest
from .review import ReviewQueue

class ActionBoundTrustStore(TrustStore):
    def __init__(self,root,expected_registry_sha256,review_root,pinned_files):
        super().__init__(root,expected_registry_sha256)
        self.review_root=Path(review_root);self.pinned_files=dict(pinned_files)
        require('reviewer_policy.json' in self.pinned_files,'MISSING_REVIEW_POLICY_BINDING','Release must pin reviewer policy independently of submitted data')
    def approved(self,kind,name,scopes):
        raw,approval=super().approved(kind,name,scopes)
        for filename,expected in self.pinned_files.items():
            p=(self.review_root/filename).resolve()
            require(p.is_relative_to(self.review_root.resolve()) and digest(p.read_bytes())==expected,'REVIEW_ACTION_CHANGED','Review history/policy differs from release')
        # Every observed event must be pinned too; adding a new action requires a new release.
        require({p.name for p in (self.review_root/'review_events').glob('*.json')}=={Path(n).name for n in self.pinned_files if n.startswith('review_events/')},'UNPINNED_REVIEW_ACTION','Unpinned review event')
        queue=ReviewQueue(self.review_root)
        needed=set(scopes)|({'reuse_rights'} if kind in ('datasets','evidence') else set())
        _,event=queue.approved(approval.get('review_subject_path'),needed,parse_json=kind!='evidence')
        require(event['policy_scope']=='PRODUCTION','TEST_DATA_FORBIDDEN','Synthetic review actions cannot authorize production')
        require(event['subject_sha256']==digest(raw),'REVIEW_SUBJECT_MISMATCH','Approved subject differs from registry input')
        require(event['actor']==approval.get('reviewed_by'),'REVIEW_ACTOR_MISMATCH','Registry actor differs from explicit action')
        return raw,approval
