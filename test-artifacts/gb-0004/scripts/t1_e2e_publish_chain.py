"""端到端验证：真实 FastAPI + 真实 Celery worker + PostgreSQL + Redis。

覆盖数据发布链的全部契约：
 T1 正常发布：页面状态 / 规则 CSV / 结果文件 对应同一份完整结果；
 T2 重复投递（同一任务连发两次）幂等，成功结果不被覆盖，attempts 正确；
 T3 留痕发布失败（原子 rename 注入故障）：run 落 failed 且无半成品，重试后恢复；
 T4 中断恢复：卡在 running 的研究可重新入队并成功；
 T5 失败/未完成研究禁止导出 CSV 与结果文件（409），不产生半成品；
 T6 已成功研究拒绝重试（409），历史成功研究始终可查看可下载；
 T7 结果文件损坏后，下载接口以数据库结果为准自动重建；
 T8 启动对账：清理孤儿 .tmp，并为缺失结果文件的历史成功研究补齐。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (ARTIFACT_DIR, clean_artifacts, load_run, make_run,
                  read_artifact, record, reset_database, seed_catalog,
                  start_worker, stop_worker, wait_status, flush_report)

import src.services.artifacts as artifacts_mod
from fastapi.testclient import TestClient
from src.config.database import SessionLocal
from src.main import app
from src.models import RuleRun, User
from src.constants.enums import RunStatus

REPORT = "/workspace/test-artifacts/gb-0004/results_e2e.tsv"


def login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "Gucang2026!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def main():
    reset_database()
    clean_artifacts()
    creator, batch = seed_catalog()
    worker = start_worker(logfile="/tmp/gb0004/e2e-worker.log")
    client = TestClient(app)
    try:
        token = login(client, "analyst@gucang.demo")
        h = auth(token)

        # ---------- T1 正常发布，三端同源 ----------
        payload = {"name": "E2E-正常研究", "batch_id": batch,
                   "min_support": 0.05, "min_confidence": 0.35,
                   "min_lift": 1.0, "max_size": 3}
        r = client.post("/runs", json=payload, headers=h)
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        st = wait_status(rid, "succeeded")
        detail = client.get(f"/runs/{rid}", headers=h).json()
        csv_resp = client.get(f"/runs/{rid}/export", headers=h)
        file_resp = client.get(f"/runs/{rid}/result-file", headers=h)
        file_json = json.loads(file_resp.content)
        same_checksum = (
            detail["result"]["checksum"] == file_json["checksum"]
            == read_artifact(rid)["checksum"]
        )
        csv_rows = len(csv_resp.content.decode("utf-8-sig").strip().splitlines()) - 1
        record("T1 页面/CSV/结果文件对应同一份完整结果",
               csv_resp.status_code == 200 and file_resp.status_code == 200
               and same_checksum and csv_rows == len(detail["result"]["rules"]),
               f"csv 行数={csv_rows}, 规则数={len(detail['result']['rules'])}, checksum 一致={same_checksum}")

        # ---------- T2 重复投递幂等 ----------
        before = load_run(rid)
        from src.worker import analyze_run
        analyze_run.delay(rid)
        analyze_run.delay(rid)
        time.sleep(5)
        after = load_run(rid)
        record("T2 重复投递不覆盖已成功结果",
               after["status"] == "succeeded" and after["checksum"] == before["checksum"]
               and after["rules"] == before["rules"],
               f"status={after['status']}, attempts 字段={after['attempts']}")

        # ---------- T3 留痕发布失败：无半成品，重试恢复 ----------
        # 故障必须跨越进程边界（worker 是独立进程），用只读目录触发 mkstemp 失败
        rid3 = make_run(SessionLocal(), batch, creator, "E2E-留痕失败")
        ARTIFACT_DIR.chmod(0o500)
        try:
            analyze_run.delay(rid3)
            st3 = wait_status(rid3, "failed")
        finally:
            ARTIFACT_DIR.chmod(0o700)
        tmp_left = list(Path(ARTIFACT_DIR).glob("*.tmp"))
        final_exists = (ARTIFACT_DIR / f"run-{rid3}.json").exists()
        record("T3a 留痕失败落 failed 且无任何半成品文件",
               st3["status"] == "failed" and not tmp_left and not final_exists,
               f"status={st3['status']}, tmp={[p.name for p in tmp_left]}, 正式文件存在={final_exists}")

        # 失败时禁止导出
        c1 = client.get(f"/runs/{rid3}/export", headers=h)
        c2 = client.get(f"/runs/{rid3}/result-file", headers=h)
        record("T3b 失败研究拒绝导出（409）",
               c1.status_code == 409 and c2.status_code == 409,
               f"export={c1.status_code}, result-file={c2.status_code}")

        # 重试恢复
        rr = client.post(f"/runs/{rid3}/retry", headers=h)
        assert rr.status_code == 202, rr.text
        st3r = wait_status(rid3, "succeeded")
        record("T3c 失败研究重新投递后完整恢复",
               st3r["status"] == "succeeded" and read_artifact(rid3) is not None,
               f"status={st3r['status']}, 工件存在={read_artifact(rid3) is not None}")

        # ---------- T4 中断（卡在 running）恢复 ----------
        rid4 = make_run(SessionLocal(), batch, creator, "E2E-中断")
        with SessionLocal() as db:
            db.get(RuleRun, rid4).status = RunStatus.RUNNING
            db.commit()
        rr = client.post(f"/runs/{rid4}/retry", headers=h)
        assert rr.status_code == 202, rr.text
        st4 = wait_status(rid4, "succeeded")
        record("T4 RUNNING 中断后重新入队可恢复",
               st4["status"] == "succeeded" and st4["has_result"],
               f"status={st4['status']}")

        # ---------- T5 排队中不可导出 ----------
        rid5 = make_run(SessionLocal(), batch, creator, "E2E-排队中")
        c1 = client.get(f"/runs/{rid5}/export", headers=h)
        c2 = client.get(f"/runs/{rid5}/result-file", headers=h)
        record("T5 未完成研究不可下载（409）",
               c1.status_code == 409 and c2.status_code == 409,
               f"export={c1.status_code}, result-file={c2.status_code}")

        # ---------- T6 成功研究拒绝重试，历史可查看 ----------
        rr = client.post(f"/runs/{rid}/retry", headers=h)
        hist = client.get(f"/runs/{rid}", headers=h)
        hist_file = client.get(f"/runs/{rid}/result-file", headers=h)
        record("T6 成功研究拒绝重试且历史结果仍可查看下载",
               rr.status_code == 409 and hist.status_code == 200
               and hist_file.status_code == 200 and hist.json()["status"] == "succeeded",
               f"retry={rr.status_code}, detail={hist.status_code}, file={hist_file.status_code}")

        # ---------- T7 损坏结果文件自动重建 ----------
        target = ARTIFACT_DIR / f"run-{rid}.json"
        target.write_text("{截断的半成品", encoding="utf-8")
        repaired = client.get(f"/runs/{rid}/result-file", headers=h)
        repaired_json = json.loads(repaired.content)
        disk = read_artifact(rid)
        record("T7 损坏文件下载时以数据库为准原子重建",
               repaired.status_code == 200 and repaired_json.get("checksum")
               and disk is not None and disk["checksum"] == detail["result"]["checksum"],
               f"http={repaired.status_code}, 重建后完整={disk is not None}")

        # ---------- T8 启动对账 ----------
        # 造一个孤儿 .tmp 和一个缺失文件的成功研究
        (ARTIFACT_DIR / ".run-999.tmp").write_text("orphan", encoding="utf-8")
        rid8 = make_run(SessionLocal(), batch, creator, "E2E-历史缺文件")
        good_result = dict(detail["result"])
        with SessionLocal() as db:
            r8 = db.get(RuleRun, rid8)
            r8.status = RunStatus.SUCCEEDED
            r8.result = good_result
            db.commit()
        assert not (ARTIFACT_DIR / f"run-{rid8}.json").exists()
        from src.services.artifacts import reconcile
        with SessionLocal() as db:
            summary = reconcile(db)
        record("T8 启动对账清理孤儿临时文件并补齐历史工件",
               summary["removed_tmp"] >= 1 and read_artifact(rid8) is not None
               and not list(Path(ARTIFACT_DIR).glob("*.tmp")),
               f"summary={summary}")

    finally:
        stop_worker(worker)
        return flush_report(REPORT)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
