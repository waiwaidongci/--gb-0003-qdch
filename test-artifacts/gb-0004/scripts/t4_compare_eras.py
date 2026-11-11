"""同一故障场景在修复前/后代码上的对照验证（BACKEND_ERA=old|new）。

old（初始提交）：无行锁、先写文件后落库、except 直接标 failed。用“两个执行都通过
开头检查、失败执行在成功执行之后写坏文件”的竞态，复现成功结果被标 failed、磁盘
残留截断文件。

new（修复后）：发布与置成功在同一行锁内。用计数器让第一次发布失败、并发重跑成功，
再证明成功终态下的失败尝试无法覆盖结果。两个时代都不允许在持锁时阻塞，避免自锁。
"""
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (clean_artifacts, load_run, make_run, read_artifact,
                  record, reset_database, seed_catalog, flush_report)

from src.config.database import SessionLocal
from src.worker import analyze_run

ERA = os.environ.get("BACKEND_ERA", "new")
REPORT = f"/workspace/test-artifacts/gb-0004/results_compare_{ERA}.tsv"


def run_old(creator, batch):
    import src.worker as wm
    rid = make_run(SessionLocal(), batch, creator, "对照-old")
    orig = Path.write_text
    tid = {}
    a_done, b_reached = threading.Event(), threading.Event()

    def fake(self, data, *a, **k):
        if threading.get_ident() == tid.get("t"):
            b_reached.set(); a_done.wait(30)
            orig(self, data[: max(1, len(data) // 3)], *a, **k)  # 截断好文件
            raise OSError("注入故障：留痕写入失败")
        return orig(self, data, *a, **k)

    wm.Path.write_text = fake

    def run_b():
        tid["t"] = threading.get_ident()
        analyze_run(rid)

    tb = threading.Thread(target=run_b); tb.start()
    assert b_reached.wait(30)
    try:
        analyze_run(rid)
    finally:
        a_done.set(); tb.join(30); wm.Path.write_text = orig
    return rid


def run_new(creator, batch):
    import src.services.artifacts as am
    rid = make_run(SessionLocal(), batch, creator, "对照-new")
    orig = am.os.replace
    budget = {"n": 1}

    def fake(src, dst, *a, **k):
        if budget["n"] > 0:
            budget["n"] -= 1
            raise OSError("注入故障：原子发布失败")
        return orig(src, dst, *a, **k)

    am.os.replace = fake
    try:
        analyze_run(rid)  # 第一次发布失败 -> failed
        threads = [threading.Thread(target=analyze_run, args=(rid,)) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join(30)
    finally:
        am.os.replace = orig
    return rid


def main():
    reset_database()
    clean_artifacts()
    creator, batch = seed_catalog()
    rid = run_old(creator, batch) if ERA == "old" else run_new(creator, batch)

    state = load_run(rid)
    art = read_artifact(rid)
    complete = bool(art and isinstance(art.get("rules"), list)
                    and art.get("checksum") and not art.get("_corrupt"))
    record(f"[{ERA}] 故障后研究保持 succeeded（成功结果不被覆盖）",
           state["status"] == "succeeded",
           f"status={state['status']}, error={state['error']!r}")
    record(f"[{ERA}] 成功结果保留且规则数正确",
           state["has_result"] and state["rules"] == 5,
           f"has_result={state['has_result']}, rules={state['rules']}")
    record(f"[{ERA}] 结果文件完整、无半成品",
           complete, f"工件完整={complete}")
    return flush_report(REPORT)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
