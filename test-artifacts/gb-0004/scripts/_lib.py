"""gb-0004 故障场景验证公共库。

使用真实 PostgreSQL（行锁/事务）+ 真实 Redis（Celery 投递）。
脚本只依赖后端源码（PYTHONPATH 指向 backend），自身放在 test-artifacts 下。
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import delete, select

from src.config.database import Base, SessionLocal, engine
from src.constants.enums import RunStatus
from src.models import Product, Receipt, ReceiptBatch, RuleRun, User
from src.utils.security import hash_password

ARTIFACT_DIR = Path(os.environ["ARTIFACT_DIR"])
RESULTS = []


def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_catalog():
    """放入 3 个商品与一个 60 篮的小批次，计算快、结果确定。"""
    with SessionLocal() as db:
        user = User(email="analyst@gucang.demo", name="测试研究员",
                    role="analyst", password_hash=hash_password("Gucang2026!"))
        db.add(user)
        db.add_all([
            Product(sku="A", name="商品A", category="c", price=10.0, cost=4.0),
            Product(sku="B", name="商品B", category="c", price=12.0, cost=5.0),
            Product(sku="C", name="商品C", category="c", price=8.0, cost=3.0),
        ])
        batch = ReceiptBatch(name="故障验证批次 · 60篮",
                             filename="fault-fixture.jsonl", checksum="fixture")
        db.add(batch)
        db.flush()
        baskets = []
        for i in range(60):
            if i % 3 == 0:
                items = ["A", "B"]
            elif i % 3 == 1:
                items = ["A", "B", "C"]
            else:
                items = ["B", "C"]
            baskets.append(Receipt(batch_id=batch.id,
                                   reference=f"F-{i:03d}", items=items))
        db.add_all(baskets)
        db.commit()
        return user.id, batch.id


def make_run(db, batch_id, creator_id, name="故障场景研究"):
    run = RuleRun(name=name, batch_id=batch_id, creator_id=creator_id,
                  min_support=0.05, min_confidence=0.35, min_lift=1.0,
                  max_size=3, status=RunStatus.QUEUED)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id


def load_run(run_id):
    with SessionLocal() as db:
        run = db.get(RuleRun, run_id)
        return {
            "id": run.id, "status": run.status, "error": run.error,
            "attempts": getattr(run, "attempts", None),
            "has_result": bool(run.result),
            "rules": len(run.result.get("rules", [])) if run.result else 0,
            "checksum": (run.result or {}).get("checksum"),
        }


def artifact_path(run_id):
    return ARTIFACT_DIR / f"run-{run_id}.json"


def read_artifact(run_id):
    p = artifact_path(run_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_corrupt": True, "_size": p.stat().st_size}


def list_artifact_files():
    return sorted(p.name for p in ARTIFACT_DIR.glob("run-*"))


def clean_artifacts():
    if ARTIFACT_DIR.exists():
        shutil.rmtree(ARTIFACT_DIR)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def start_worker(env_extra=None, logfile="/tmp/gb0004/worker.log"):
    """启动真实 Celery worker（prefork，concurrency=1）。"""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    log = open(logfile, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-m", "celery", "-A", "src.worker.app", "worker",
         "--loglevel=info", "--concurrency=1",
         "-n", f"w{int(time.time()*1000)%100000}@%h"],
        cwd="/workspace/backend", env=env, stdout=log, stderr=log,
    )
    _wait_for_worker(env, proc)
    return proc


def _wait_for_worker(env, proc, timeout=30):
    from celery import Celery
    app = Celery(broker=env["REDIS_URL"], backend=env["REDIS_URL"])
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("worker 提前退出")
        try:
            replies = app.control.ping(timeout=1)
            if replies:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("worker 未在超时内就绪")


def stop_worker(proc):
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def wait_status(run_id, expected, timeout=60):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = load_run(run_id)
        if last["status"] == expected:
            return last
        time.sleep(0.3)
    raise AssertionError(f"run {run_id} 未在 {timeout}s 内到达 {expected}，最后状态={last}")


def record(case, ok, detail):
    RESULTS.append((case, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {case} :: {detail}")


def flush_report(path):
    Path(path).write_text(
        "\n".join(f"{'PASS' if ok else 'FAIL'}\t{case}\t{detail}"
                  for case, ok, detail in RESULTS) + "\n",
        encoding="utf-8")
    failed = [c for c, ok, _ in RESULTS if not ok]
    print(f"\n合计 {len(RESULTS)} 项，失败 {len(failed)} 项")
    return not failed
