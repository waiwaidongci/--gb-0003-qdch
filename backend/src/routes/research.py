from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers,admins
from src.controllers.research import export_rules,export_proposals
from src.services import runs,proposals
from src.schemas.run import RunInput
from src.schemas.proposal import ProposalInput,ReviewInput
from src.utils.serialize import row
router=APIRouter(tags=['research'])
@router.get('/runs')
def all_runs(db:Session=Depends(get_db),user=Depends(current_user)): return runs.list_runs(db)
@router.post('/runs',status_code=201)
def queue(data:RunInput,db:Session=Depends(get_db),user=Depends(writers)): return runs.create_run(db,data,user)
@router.get('/runs/{id}')
def detail(id:int,db:Session=Depends(get_db),user=Depends(current_user)): return row(runs.get_run(db,id))
@router.get('/runs/{id}/export')
def export(id:int,db:Session=Depends(get_db),user=Depends(current_user)): return export_rules(db,id)
@router.get('/proposals')
def all_proposals(db:Session=Depends(get_db),user=Depends(current_user)): return proposals.list_proposals(db)
@router.post('/proposals',status_code=201)
def add(data:ProposalInput,db:Session=Depends(get_db),user=Depends(writers)): return proposals.create_proposal(db,data,user)
@router.patch('/proposals/{id}/review')
def review(id:int,data:ReviewInput,db:Session=Depends(get_db),user=Depends(admins)): return proposals.review_proposal(db,id,data,user)
@router.get('/proposals-export')
def export_all(db:Session=Depends(get_db),user=Depends(current_user)): return export_proposals(db)
