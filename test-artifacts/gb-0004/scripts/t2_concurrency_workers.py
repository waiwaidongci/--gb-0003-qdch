"""跨进程并发验证：两个真实 Celery worker 同时执行同一研究。

旧代码的缺口是“同一 run 的两个执行都通过开头检查”，失败执行随后覆盖成功结果。
本测试用两个独立 worker 进程，并在投递前把工件目录设为只读，制造确定性的
留痕发布失败；同一研究连发两次，两个 worker 并发争抢同一行：
  - 行锁保证同一时刻只有一个执行能认领该 run；
  - 发布失败的执行只把“未成功的 run”标记 failed，且不留下半成品；
  - 恢复可写并重新投递后，研究完整成功（失败尝试无法污染最终结果）。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (ARTIFACT_DIR, clean_artifacts, load_run, make_run,
                  read_artifact, record, reset_database, seed_catalog,
                  start_worker, stop_worker, wait_status, flush_report)

from src.config.database import SessionLocal
from src.worker import analyze_run

REPORT = "/workspace/test-artifacts/gb-0004/results_concurrency.tsv"


def main():
    reset_database()
    clean_artifacts()
    creator, batch = seed_catalog()
    rid = make_run(SessionLocal(), batch, creator, "跨进程并发-同一研究")

    w1 = start_worker(logfile="/tmp/gb0004/conc-w1.log")
    w2 = start_worker(logfile="/tmp/gb0004/conc-w2.log")
    try:
        # 投递前令留痕发布必然失败；同一研究连发两次，两个 worker 并发处理
        ARTIFACT_DIR.chmod(0o500)
        analyze_run.delay(rid)
        analyze_run.delay(rid)
        failed = wait_status(rid, "failed", timeout=40)
        tmp_left = list(Path(ARTIFACT_DIR).glob("*.tmp"))
        final_file = ARTIFACT_DIR / f"run-{rid}.json"
        record("C1 并发执行在留痕失败后安全落 failed",
               failed["status"] == "failed" and failed["has_result"] is False,
               f"status={failed['status']}, has_result={failed['has_result']}")
        record("C2 失败不产生任何半成品（无 .tmp、无正式文件）",
               not tmp_left and not final_file.exists(),
               f"tmp={[p.name for p in tmp_left]}, 正式文件存在={final_file.exists()}")

        # 恢复可写并重新投递：行锁串行化后研究应完整成功
        ARTIFACT_DIR.chmod(0o700)
        analyze_run.delay(rid)
        ok = wait_status(rid, "succeeded", timeout=60)
        artifact = read_artifact(rid)
        record("C3 重新投递后研究完整成功，数据库结果与结果文件一致",
               ok["status"] == "succeeded" and ok["rules"] == 5
               and artifact is not None and artifact["receipt_count"] == 60
               and artifact["checksum"] == ok["checksum"],
               f"status={ok['status']}, rules={ok['rules']}, checksum 一致={artifact and artifact['checksum'] == ok['checksum']}")

        # 再连发两次重复投递，成功终态必须稳定，attempts 不再增长（已成功直接跳过）
        before = load_run(rid)["attempts"]
        analyze_run.delay(rid)
        analyze_run.delay(rid)
        import time
        time.sleep(5)
        after = load_run(rid)
        record("C4 成功终态对重复投递幂等，结果不被覆盖",
               after["status"] == "succeeded" and after["checksum"] == ok["checksum"]
               and after["attempts"] == before,
               f"attempts {before} -> {after}, status={after['status']}")
    finally:
        os.chmod(ARTIFACT_DIR, 0o700)
        stop_worker(w1)
        stop_worker(w2)
        return flush_report(REPORT)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
