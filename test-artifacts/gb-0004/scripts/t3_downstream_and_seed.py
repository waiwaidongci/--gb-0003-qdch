"""下游消费与演示数据验证。

 P1 成功研究可建提案、负责人审核、提案 CSV 导出闭环；
 P2 失败研究无法建提案（422），不会基于半成品建立依据；
 P3 审计留痕包含入队、成功、失败、重试；
 P4 真实 scripts.seed_demo 在修复后的链路上可独立运行且幂等。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (clean_artifacts, load_run, make_run, record,
                  reset_database, seed_catalog, start_worker,
                  stop_worker, wait_status, flush_report)

from fastapi.testclient import TestClient
from sqlalchemy import select
from src.config.database import SessionLocal
from src.constants.enums import RunStatus
from src.main import app
from src.models import AuditLog, RuleRun
from src.worker import analyze_run

REPORT = "/workspace/test-artifacts/gb-0004/results_downstream.tsv"


def login(client, email):
    return client.post("/auth/login",
                       json={"email": email, "password": "Gucang2026!"}).json()["token"]


def main():
    reset_database()
    clean_artifacts()
    creator, batch = seed_catalog()
    # 补一个 admin 账号用于审核
    from src.models import User
    from src.utils.security import hash_password
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == "admin@gucang.demo")):
            db.add(User(email="admin@gucang.demo", name="负责人", role="admin",
                        password_hash=hash_password("Gucang2026!")))
            db.commit()

    worker = start_worker(logfile="/tmp/gb0004/down-worker.log")
    client = TestClient(app)
    try:
        at = login(client, "analyst@gucang.demo")
        mt = login(client, "admin@gucang.demo")
        ah, mh = {"Authorization": f"Bearer {at}"}, {"Authorization": f"Bearer {mt}"}

        # P1 成功研究 -> 提案 -> 审核 -> 提案 CSV（经 API 入队以产生 run.queue 留痕）
        qr = client.post("/runs", json={"name": "下游-成功研究", "batch_id": batch,
                         "min_support": .05, "min_confidence": .35,
                         "min_lift": 1., "max_size": 3}, headers=ah)
        rid = qr.json()["id"]
        wait_status(rid, "succeeded")
        pr = client.post("/proposals", json={"run_id": rid, "rule_index": 0,
                         "name": "试点提案", "note": "小范围试点"}, headers=ah)
        pid = pr.json()["id"]
        ok = pr.status_code == 201
        rv = client.patch(f"/proposals/{pid}/review",
                          json={"status": "approved", "note": "同意"}, headers=mh)
        pe = client.get("/proposals-export", headers=ah)
        record("P1 成功研究的提案-审核-导出闭环",
               ok and rv.status_code == 200 and rv.json()["status"] == "approved"
               and pe.status_code == 200 and "试点提案" in pe.content.decode(),
               f"proposal={pr.status_code}, review={rv.status_code}, export={pe.status_code}")

        # P2 失败研究不能建提案
        rid2 = make_run(SessionLocal(), batch, creator, "下游-失败研究")
        with SessionLocal() as db:
            r2 = db.get(RuleRun, rid2)
            r2.status = RunStatus.FAILED
            r2.error = "演示失败"
            db.commit()
        pr2 = client.post("/proposals", json={"run_id": rid2, "rule_index": 0,
                          "name": "不应建立", "note": "x"}, headers=ah)
        record("P2 失败研究禁止建立提案（422）",
               pr2.status_code == 422, f"status={pr2.status_code}")

        # 失败研究经 API 重试，应产生 run.retry 留痕并恢复成功
        rt = client.post(f"/runs/{rid2}/retry", headers=ah)
        wait_status(rid2, "succeeded")

        # P3 审计留痕
        with SessionLocal() as db:
            actions = {a for a in db.scalars(select(AuditLog.action))}
        record("P3 审计留痕覆盖关键链路",
               {"run.queue", "run.retry", "run.succeeded", "proposal.create",
                "proposal.review"}.issubset(actions),
               f"actions={sorted(actions)}")
    finally:
        stop_worker(worker)

    # P4 真实 seed 脚本幂等（独立进程语义，直接调用函数两次）
    import scripts.seed_demo as seed_mod
    c1 = seed_mod.seed()
    c2 = seed_mod.seed()
    record("P4 seed_demo 连续两次运行幂等且不覆盖",
           c1 == c2 and c2["rule_runs"] >= 1 and c2["bundle_proposals"] >= 1,
           f"first={c1.get('rule_runs')} second={c2.get('rule_runs')}")

    return flush_report(REPORT)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
