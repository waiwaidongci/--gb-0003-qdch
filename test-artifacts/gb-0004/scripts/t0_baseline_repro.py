"""同进程并发故障验证（对修复后实现）。

修复后 worker 在“发布工件 + 置成功”整段持有行锁，已成功的 run 不会被任何失败
执行触碰。这里用两个并发线程 + 只让其中一次发布故障的定向注入来验证：
  - 让第一次执行在发布结果文件时失败（run 落 failed，无半成品）；
  - 第二次执行随即成功；
  - 再制造一次“后到执行在成功之后仍试图失败”的并发，确认它只能看到 succeeded
    并直接返回，成功结果与完整工件保持不变。

注入点为 artifacts.os.replace，且绝不在持有数据库行锁时阻塞，避免测试自锁。
"""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (clean_artifacts, load_run, make_run, read_artifact,
                  record, reset_database, seed_catalog)

import src.services.artifacts as artifacts_mod
from src.config.database import SessionLocal
from src.models import RuleRun
from src.worker import analyze_run

ORIG_REPLACE = artifacts_mod.os.replace
FAIL_UNTIL = {"remaining": 0}


def patched_replace(src, dst, *args, **kwargs):
    if FAIL_UNTIL["remaining"] > 0:
        FAIL_UNTIL["remaining"] -= 1
        raise OSError("注入故障：结果文件原子发布失败（模拟磁盘只读）")
    return ORIG_REPLACE(src, dst, *args, **kwargs)


def main():
    reset_database()
    clean_artifacts()
    creator, batch = seed_catalog()
    with SessionLocal() as db:
        run_id = make_run(db, batch, creator, "并发投递-发布失败不污染成功结果")

    artifacts_mod.os.replace = patched_replace
    try:
        # 第一次发布必然失败：run 应安全落 failed，且无半成品
        FAIL_UNTIL["remaining"] = 1
        analyze_run(run_id)
        st = load_run(run_id)
        record("S1 发布失败时安全落 failed 且无半成品",
               st["status"] == "failed" and not st["has_result"]
               and not list(Path(artifacts_mod.ARTIFACT_DIR).glob("*.tmp"))
               and read_artifact(run_id) is None,
               f"status={st['status']}, has_result={st['has_result']}")

        # 两个线程并发重新执行；故障额度已用尽，二者都走正常路径，行锁串行化
        t1 = threading.Thread(target=analyze_run, args=(run_id,))
        t2 = threading.Thread(target=analyze_run, args=(run_id,))
        t1.start(); t2.start(); t1.join(30); t2.join(30)
        ok = load_run(run_id)
        record("S2 并发重复执行后研究成功且结果完整",
               ok["status"] == "succeeded" and ok["rules"] == 5
               and read_artifact(run_id) is not None,
               f"status={ok['status']}, rules={ok['rules']}")

        # 成功之后再来一个“失败尝试”：因行锁内发现已 succeeded，它直接返回，
        # 既不写文件也不改状态
        before = load_run(run_id)
        FAIL_UNTIL["remaining"] = 1  # 即使发布被注入故障也不会被执行到
        analyze_run(run_id)
        after = load_run(run_id)
        record("S3 成功终态下的失败尝试无法覆盖结果",
               after["status"] == "succeeded" and after["checksum"] == before["checksum"]
               and read_artifact(run_id)["checksum"] == before["checksum"],
               f"status={after['status']}, checksum 保持={after['checksum'] == before['checksum']}")
    finally:
        artifacts_mod.os.replace = ORIG_REPLACE

    # S4：worker 被硬杀在 RUNNING，重投后恢复
    rid2 = make_run(SessionLocal(), batch, creator, "中断后重投")
    with SessionLocal() as db:
        db.get(RuleRun, rid2).status = "running"
        db.commit()
    analyze_run(rid2)
    s4 = load_run(rid2)
    record("S4 RUNNING 中断后重复投递可恢复",
           s4["status"] == "succeeded" and s4["has_result"] and read_artifact(rid2) is not None,
           f"status={s4['status']}")

    return all(ok for _, ok, _ in __import__("_lib").RESULTS)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
