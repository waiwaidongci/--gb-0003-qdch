from fastapi import HTTPException
from sqlalchemy import select

from src.constants.enums import RunStatus
from src.models import RuleRun, ReceiptBatch
from src.utils.serialize import row
from .audit import record


def list_runs(db):
    return [row(r) for r in db.scalars(select(RuleRun).order_by(RuleRun.id.desc()))]


def get_run(db, id):
    run = db.get(RuleRun, id)
    if not run:
        raise HTTPException(404, '规则实验不存在')
    return run


def create_run(db, data, user):
    if not db.get(ReceiptBatch, data.batch_id):
        raise HTTPException(404, '批次不存在')
    run = RuleRun(**data.model_dump(), creator_id=user.id)
    db.add(run)
    db.commit()
    _enqueue(run.id, db, user)
    return row(run)


def retry_run(db, id, user):
    """对失败或中断（卡在 running/queued）的研究重新入队。

    已成功的研究拒绝重试：成功结果是终态，不允许被新尝试覆盖。
    历史成功研究始终保留可查看，不受重试影响。
    """
    run = get_run(db, id)
    if run.status == RunStatus.SUCCEEDED:
        raise HTTPException(409, '该研究已成功，结果为终态，无需重试')
    run.status = RunStatus.QUEUED
    run.error = None
    db.commit()
    _enqueue(run.id, db, user, action='run.retry')
    return row(run)


def _enqueue(run_id, db, user, action='run.queue'):
    from src.worker import analyze_run
    try:
        analyze_run.delay(run_id)
    except Exception:
        # 仅当研究尚未成功时才回写排队失败，绝不影响已成功结果
        run = db.get(RuleRun, run_id)
        if run is not None and run.status != RunStatus.SUCCEEDED:
            run.status = RunStatus.FAILED
            run.error = '队列不可用，请重新提交'
            db.commit()
        raise HTTPException(503, '队列不可用，请重新提交')
    record(db, user.email, action, {'run_id': run_id})
