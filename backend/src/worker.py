import logging

from celery import Celery
from sqlalchemy import select

from src.config.settings import REDIS_URL
from src.config.database import SessionLocal
from src.models import RuleRun, Receipt, Product
from src.services.apriori import mine_rules
from src.services.artifacts import publish_artifact
from src.services.audit import record
from src.constants.enums import RunStatus

app = Celery('basket_forge', broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(task_track_started=True, worker_prefetch_multiplier=1, task_acks_late=True)


@app.task(name='basket.analyze', soft_time_limit=120, time_limit=150)
def analyze_run(id):
    """同一研究的重复投递/并发执行在此串行化且互不覆盖。

    关键保证：
    - 用 SELECT ... FOR UPDATE 锁定该行，同一 run 的并发执行排队执行，
      先完成的成功结果不会被后到者覆盖；
    - 已成功的 run 直接跳过（幂等）；
    - 结果先原子写入结果文件，成功后才在同一事务里把状态置为 succeeded；
      留痕失败则整笔回滚，run 回到 failed，数据库里不存在“成功但文件残缺”的组合；
    - 失败只写入当前执行自己拿到的未完成 run，绝不触碰已成功结果；
    - worker 在 RUNNING 中被硬杀后，acks_late 重投会重新认领并恢复。
    """
    with SessionLocal() as db:
        # 行锁：并发的同一任务在此排队；不同 run 锁不同行，互不阻塞
        run = db.scalar(select(RuleRun).where(RuleRun.id == id).with_for_update())
        if not run:
            logging.warning("analyze_run: run %s 不存在，忽略", id)
            return
        if run.status == RunStatus.SUCCEEDED:
            return  # 幂等：重复投递已成功研究，直接结束

        run.status = RunStatus.RUNNING
        run.attempts = (run.attempts or 0) + 1
        db.commit()  # 认领后先释放行锁，避免长计算阻塞同 run 的后续重投

    try:
        with SessionLocal() as db:
            baskets = list(db.scalars(
                select(Receipt.items).where(Receipt.batch_id == run.batch_id).order_by(Receipt.id)))
            products = {p.sku: {'price': p.price, 'cost': p.cost}
                        for p in db.scalars(select(Product))}
        result = mine_rules(baskets, products, run.min_support,
                            run.min_confidence, run.min_lift, run.max_size)

        with SessionLocal() as db:
            # 发布阶段再次加行锁：只有确认自己仍是“未成功的现任执行”才允许发布，
            # 已成功则直接返回，连结果文件都不触碰，杜绝重复执行覆盖既有工件
            current = db.scalar(select(RuleRun).where(RuleRun.id == id).with_for_update())
            if current is None or current.status == RunStatus.SUCCEEDED:
                return

            # 留痕原子发布与状态置成功放在同一把锁/同一事务边界内：
            # 发布失败即抛错回滚，由 _mark_failed 安全落账，半成品只可能是 .tmp 并被清理
            publish_artifact(id, result)
            current.result = result
            current.status = RunStatus.SUCCEEDED
            current.error = None
            db.commit()
        record(SessionLocal(), 'worker', 'run.succeeded',
               {'run_id': id, 'rules': len(result['rules']), 'attempts': run.attempts})
    except Exception as e:  # noqa: BLE001 - 任何失败都要安全落账，不能污染成功结果
        logging.exception("analyze_run %s 失败", id)
        _mark_failed(id, str(e)[:1000])


def _mark_failed(run_id, message):
    """只把仍未成功的 run 标记失败；已成功结果永不被失败尝试覆盖。"""
    with SessionLocal() as db:
        current = db.scalar(select(RuleRun).where(RuleRun.id == run_id).with_for_update())
        if current is None or current.status == RunStatus.SUCCEEDED:
            return
        current.status = RunStatus.FAILED
        current.error = message
        db.commit()
    record(SessionLocal(), 'worker', 'run.failed', {'run_id': run_id, 'error': message})
