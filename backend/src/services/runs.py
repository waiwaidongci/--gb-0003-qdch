from sqlalchemy import select
from fastapi import HTTPException
from src.models import RuleRun,ReceiptBatch
from src.utils.serialize import row
from .audit import record
from src.constants.enums import RunStatus
def list_runs(db): return [row(r) for r in db.scalars(select(RuleRun).order_by(RuleRun.id.desc()))]
def get_run(db,id):
 run=db.get(RuleRun,id)
 if not run: raise HTTPException(404,'规则实验不存在')
 return run
def create_run(db,data,user):
 if not db.get(ReceiptBatch,data.batch_id): raise HTTPException(404,'批次不存在')
 run=RuleRun(**data.model_dump(),creator_id=user.id);db.add(run);db.commit()
 from src.worker import analyze_run
 try: analyze_run.delay(run.id)
 except Exception:
  run.status=RunStatus.FAILED;run.error='队列不可用，请重新提交';db.commit();raise HTTPException(503,run.error)
 record(db,user.email,'run.queue',{'run_id':run.id});return row(run)
