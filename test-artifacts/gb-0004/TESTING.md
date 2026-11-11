# gb-0004 规则研究数据发布链修复 —— 故障场景验证报告

日期：2026-11-11　范围：收据批次规则研究（RuleRun）从入队、并发计算、留痕落盘到页面/下载发布的完整链路。

## 1. 复现到的原始缺陷

旧 `worker.analyze_run` 在任务开始只判断一次 `status != succeeded`，整个执行期间无行锁、无状态保护，且**先写结果文件、后更新数据库**。当同一研究被重复投递、两个执行并发通过开头检查后：

- 执行 A 正常完成 → `succeeded`、结果落库；
- 执行 B 的留痕（结果文件）写入失败 → 进入 `except` → 无条件把同一 run 改成 `failed`，**已成功结果被覆盖成失败**；
- 同时磁盘上残留被截断的 `run-{id}.json`，成为可被误用的半成品。

对照脚本 `t4_compare_eras.py` 对初始提交 `ecaae01` 实测（`results_compare_old.tsv`）：

| 断言 | 旧代码结果 |
|---|---|
| 故障后研究保持 succeeded | **FAIL**：status=`failed`，error=留痕写入失败 |
| 成功结果保留且规则数正确 | PASS（DB 结果仍在，但状态已被污染） |
| 结果文件完整、无半成品 | **FAIL**：工件被截断、JSON 不可解析 |

## 2. 修复设计

1. **行锁认领 + 终态保护（`worker.py`）**：用 `SELECT … FOR UPDATE` 锁定 run 行，同一研究的并发执行串行化；`succeeded` 为终态，重复投递直接跳过，任何失败尝试都不触碰已成功结果。
2. **原子留痕（新增 `services/artifacts.py`）**：结果文件经“临时文件 + `fsync` + 同目录 `os.replace`”发布，任何中途失败只可能留下 `.tmp` 并被立即清理，正式文件要么完整、要么不存在；读取时校验结构，损坏按缺失处理。
3. **发布与置成功同一锁/事务边界**：先在最终行锁内确认自己仍是现任执行，再原子发布工件、写 DB 结果、置 `succeeded`；留痕失败整笔回滚并由 `_mark_failed` 仅对“未成功 run”落 `failed`，不存在“成功但文件残缺”的组合。
4. **三端同源（`controllers/research.py`）**：页面状态、规则 CSV、结果文件下载都只接受“成功且结构完整”的结果；未完成/失败研究返回 409；结果文件缺失或损坏时以数据库成功结果为准原子重建。
5. **中断恢复与重试**：worker 在 `running` 被硬杀后，`acks_late` 重投或新增的 `POST /runs/{id}/retry` 可重新认领恢复；成功研究拒绝重试（409）；新增 `attempts` 列记录执行次数，启动时幂等迁移。
6. **启动对账（`main.py` + `artifacts.reconcile`）**：清理孤儿 `.tmp`，为历史成功研究（含 seed 基准）补齐缺失结果文件，历史研究始终可查看、可下载。

前端：结果页新增“下载结果文件”与失败研究“重新投递”，运行列表显示执行次数；失败/未完成时下载按钮禁用。`npm run build`（含 `tsc --noEmit`）通过。

## 3. 验证环境（真实组件，非 mock）

- PostgreSQL 16（用户态 conda 安装，端口 15432）验证真实行锁与事务；
- Redis 7.4.2（源码编译，端口 16379）+ 真实 Celery worker（`task_acks_late`，并发场景起两个独立 worker 进程）；
- FastAPI `TestClient` 走完整 HTTP/权限/序列化链路；
- 故障注入：只读工件目录（跨进程 IO 故障）、`os.replace`/`write_text` 定向 monkeypatch（同进程竞态）。

## 4. 测试用例与结果（合计 25 项断言，修复后全 PASS）

| 套件 | 覆盖 | 结果 |
|---|---|---|
| T0 `t0_baseline_repro.py` | 发布失败安全落 failed 无半成品、并发重复执行成功、成功终态下失败尝试无法覆盖、RUNNING 中断重投恢复 | 4/4 PASS |
| T1 `t1_e2e_publish_chain.py` | 页面/CSV/结果文件同源同 checksum、重复投递幂等、留痕失败 409 无半成品、重试恢复、中断恢复、未完成禁下载、成功拒绝重试、损坏文件自愈、启动对账 | 10/10 PASS |
| T2 `t2_concurrency_workers.py` | 两个真实 worker 并发同一 run：行锁串行、失败不污染、重试完整成功、成功终态幂等 | 4/4 PASS |
| T3 `t3_downstream_and_seed.py` | 提案-审核-CSV 闭环、失败研究禁建提案(422)、审计留痕含 queue/retry/succeeded、seed 两次幂等 | 4/4 PASS |
| T4 `t4_compare_eras.py` | 同一故障在旧代码复现 2 项 FAIL、在新代码 3/3 PASS（前后对照） | 新 3/3 PASS |

机读结果：`results_e2e.tsv`、`results_concurrency.tsv`、`results_downstream.tsv`、`results_compare_old.tsv`、`results_compare_new.tsv`。

## 5. 复跑方式

```sh
# 准备 PostgreSQL 与 Redis（连接默认见 scripts/run_all.sh，可用环境变量覆盖）
cd test-artifacts/gb-0004/scripts
./run_all.sh
```

## 6. 已知边界

- 本演示用启动时幂等 `ALTER TABLE` 代替 Alembic 增量迁移；正式环境应纳入迁移工具。
- 并发验证规模为 2 worker × 同 run；行锁方案对 N 个并发同 run 同样成立（锁不同行，不影响其他研究），未做高负载压测。
- 结果文件以数据库成功结果为唯一事实来源；文件仅作留痕与下载，损坏可自愈，不作为判定依据。
