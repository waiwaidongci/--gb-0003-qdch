from sqlalchemy import select
from fastapi import HTTPException
from src.models import BundleProposal,RuleRun
from src.utils.serialize import row
from .audit import record
from src.constants.enums import RunStatus,ProposalStatus
def list_proposals(db): return [row(p) for p in db.scalars(select(BundleProposal).order_by(BundleProposal.id.desc()))]
def create_proposal(db,data,user):
 run=db.get(RuleRun,data.run_id)
 if not run or run.status!=RunStatus.SUCCEEDED: raise HTTPException(422,'请选择已完成实验')
 rules=run.result.get('rules',[])
 if data.rule_index>=len(rules): raise HTTPException(422,'规则索引不存在')
 obj=BundleProposal(run_id=run.id,name=data.name,note=data.note,rule=rules[data.rule_index],creator_id=user.id);db.add(obj);db.commit();record(db,user.email,'proposal.create',{'proposal_id':obj.id});return row(obj)
def review_proposal(db,id,data,user):
 obj=db.get(BundleProposal,id)
 if not obj: raise HTTPException(404,'提案不存在')
 if obj.status!=ProposalStatus.DRAFT: raise HTTPException(409,'仅草稿可审核')
 obj.status=data.status;obj.note=data.note;db.commit();record(db,user.email,'proposal.review',{'proposal_id':id,'status':data.status});return row(obj)
