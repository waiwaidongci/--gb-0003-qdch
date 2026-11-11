#!/usr/bin/env bash
# gb-0004 数据发布链修复 —— 全量故障场景验证入口。
# 前置：可达的 PostgreSQL（默认 localhost:15432）与 Redis（默认 localhost:16379）。
set -u
cd "$(dirname "$0")"
set -a
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://basket:basket_demo@localhost:15432/basket}"
export REDIS_URL="${REDIS_URL:-redis://localhost:16379/0}"
export JWT_SECRET="${JWT_SECRET:-local-demo-test-secret}"
export ARTIFACT_DIR="${ARTIFACT_DIR:-/tmp/gb0004/artifacts}"
set +a

run() { echo; echo "==================== $1 ===================="; PYTHONPATH="$2" BACKEND_ERA="${3:-new}" python3 "$4" || echo "!! $1 失败"; }
run "T0 同进程并发/中断恢复"            /workspace/backend            new t0_baseline_repro.py
run "T1 端到端发布链(HTTP+真实worker)"  /workspace/backend            new t1_e2e_publish_chain.py
run "T2 跨进程双worker并发"             /workspace/backend            new t2_concurrency_workers.py
run "T3 下游提案/审计/seed"             /workspace/backend            new t3_downstream_and_seed.py

# 修复前对照：按需从初始提交检出独立 worktree（不影响当前工作区），结束后清理
OLD_WT="/tmp/gb0004/old-code"
if [ ! -d "$OLD_WT/backend" ]; then
  git -C /workspace worktree add -f --detach "$OLD_WT" ecaae01 >/dev/null
fi
echo; echo "==================== T4 修复前对照(初始提交ecaae01，预期复现缺陷) ===================="
PYTHONPATH="$OLD_WT/backend" BACKEND_ERA=old python3 t4_compare_eras.py && echo "意外：旧代码竟然通过" || echo ">> 符合预期：旧代码复现了“成功被标 failed + 半成品文件”缺陷"
run "T4 修复后对照(当前实现)"           /workspace/backend            new t4_compare_eras.py
git -C /workspace worktree remove --force "$OLD_WT" 2>/dev/null || true
echo
echo "结果 TSV："; ls -1 ../results_*.tsv 2>/dev/null
