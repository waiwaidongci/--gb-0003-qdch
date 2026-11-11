import json,os
from pathlib import Path
from celery import Celery
from sqlalchemy import select
from src.config.settings import REDIS_URL,ARTIFACT_DIR
from src.config.database import SessionLocal
from src.models import RuleRun,Receipt,Product
from src.services.apriori import mine_rules
from src.services.audit import record
from src.constants.enums import RunStatus
app=Celery('basket_forge',broker=REDIS_URL,backend=REDIS_URL)
app.conf.update(task_track_started=True,worker_prefetch_multiplier=1,task_acks_late=True)
@app.task(name='basket.analyze',soft_time_limit=120,time_limit=150)
def analyze_run(id):
 with SessionLocal() as db:
  run=db.get(RuleRun,id)
  if not run or run.status==RunStatus.SUCCEEDED: return
  run.status=RunStatus.RUNNING;db.commit()
  try:
   baskets=list(db.scalars(select(Receipt.items).where(Receipt.batch_id==run.batch_id).order_by(Receipt.id)))
   products={p.sku:{'price':p.price,'cost':p.cost} for p in db.scalars(select(Product))}
   result=mine_rules(baskets,products,run.min_support,run.min_confidence,run.min_lift,run.max_size)
   Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True)
   Path(ARTIFACT_DIR,f'run-{id}.json').write_text(json.dumps(result,ensure_ascii=False))
   run.result=result;run.status=RunStatus.SUCCEEDED;run.error=None;db.commit();record(db,'worker','run.succeeded',{'run_id':id,'rules':len(result['rules'])})
  except Exception as e:
   db.rollback();run=db.get(RuleRun,id);run.status=RunStatus.FAILED;run.error=str(e)[:1000];db.commit();record(db,'worker','run.failed',{'run_id':id,'error':run.error})
