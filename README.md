# 谷仓 · 组合选品研究室

把匿名收据中的共现关系，转成有支持数、基率与毛利依据的门店陈列试点提案。

谷仓食品工作室的 12 人选品组每周从匿名收据按商品计数，靠经验挑组合。三个痛点是热销商品造成基率误读、低支持数关系不可复算、商品毛利与组合方案脱节。这里承接匿名篮子→Apriori 研究→规则解释→负责人审核→提案 CSV 交付。所有数据均为合成数据；本项目不是交易或购物系统。

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

访问 [研究室](http://localhost:18202)；[后端交互文档](http://localhost:19202/docs)。数据库映射到 `localhost:17702`。正常会自动 seed；再次 seed 不新增、不覆盖已有自然键数据。空数据库包含 1200 张匿名收据、12 个研究商品、3 个收据批次、1 份算法真算基准研究及 1 份提案。

| 账号 | 密码 | 角色 | 典型权限 |
|---|---|---|---|
| admin@gucang.demo | Gucang2026! | admin / 选品负责人 | 阅读、新建商品/批次/研究/提案、审核 |
| analyst@gucang.demo | Gucang2026! | analyst / 商品研究员 | 阅读、新建商品/批次/研究/提案，审核返回 403 |
| viewer@gucang.demo | Gucang2026! | viewer / 门店督导 | 只读与下载；所有写入返回 403 |

## 一天的研究剧本

1. 08:30 研究员登录，确认“秋季早餐街区 · 400篮”及源文件 `gucang-autumn-baskets-1.jsonl`。
2. 在“收据与商品”打开样本，核对 OAT 燕麦拿铁与 BREAD 全麦餐包，以及商品价格和成本。
3. 在“规则实验”新建“秋季早餐组合研究”，选择该批次。
4. 设置支持度 .05、置信度 .35、提升度 1、最大项集 3。
5. 提交后，真实 Celery worker 从 PostgreSQL 读取篮子并计算，页面每 3 秒轮询状态。
6. 在结果中比较支持数、置信度、提升度，按毛利率过滤，选用一条规则。
7. 建立“早餐温暖搭档”提案；负责人登录后填写试点备注并通过或退回。
8. 门店督导在提案页下载 CSV，带着支持数和“关联不代表因果”的限制安排试点。

## 页面与职责

研究总览、收据与商品、规则实验、关联结果、组合提案、研究留痕共 6 页。RunList 被总览和规则实验复用，RuleLink 被总览、结果与提案复用。业务实体 Product、ReceiptBatch、Receipt、RuleRun、BundleProposal 贯穿数据库、schema、service、route/API、store 与页面。Receipt 只属于所属批次，API 返回前 100 张样本用于核对。批次导入最多 5000 张，JSON 数组包含 `reference` 与 `items`；界面给出可改的两张收据示例，不支持真实第三方数据源直连。

## 算法口径

`backend/src/services/apriori.py` 是纯 Python 实现。输入为去重 SKU 集合的篮子列表、SKU 售价/成本、三个阈值和最大项集大小；输出频繁项集数量、各层候选通过数、关联规则、输入 SHA-256 指纹。Apriori 连接上层频繁项集，并要求全部 k−1 子集也频繁，再对真实篮子计数。最小次数是 `ceil(N * min_support)`。枚举非空前后件，按提升度、置信度、支持度及字典序稳定排序。

- support(A→B) = count(A∪B)/N。
- confidence(A→B) = count(A∪B)/count(A)。
- lift(A→B) = confidence/support(B)。
- 理论毛利率 = (组合售价−组合成本)/组合售价；未扣折扣、损耗及陈列成本。

空篮子、未知 SKU、非法阈值、少于 2 张导入数据会被拒绝；无规则是正常空结果。固定 seed `20261112` 产生演示篮子。运行记录保留批次、参数与结果指纹；提案复制规则快照，后续新运行不会改变已审核依据。算法度量共现，无法推断因果，也没有多重假设显著性保证。最多 4 项、5000 张篮子是本地研究配额，未经大规模负载测试。

## 工程与本地开发

| 层 | 技术 |
|---|---|
| 前端 | React 18.3、TypeScript 5.7、Vite 6.4、Nginx 1.27 |
| API | Python 3.11、FastAPI、Pydantic、SQLAlchemy 2 |
| 持久化 | PostgreSQL 16、JSON 规则结果 |
| 队列 | Celery 5.4 + Kombu 5.4.2 + Redis 7，独立 worker |
| 认证 | PBKDF2-SHA256 210000 轮、JWT HS256 8 小时、服务端角色检查 |

```sh
# 后端：需本机可达 PostgreSQL 与 Redis，并设置 DATABASE_URL / REDIS_URL / JWT_SECRET
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
# worker：相同环境变量
celery -A src.worker.app worker --concurrency=1
# 前端开发可对照 nginx.conf 配置 /api/ 代理，默认生产模式由 Nginx 同源代理
cd frontend
npm ci
npm run build
```

目录：`backend/src/{config,constants,models,schemas,services,controllers,routes,middlewares,utils}`；`backend/scripts/seed_demo.py`；`backend/migrations/`；`frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}`。`migrations/001_initial.sql` 说明首次启动 metadata 建表策略；本地演示未配 Alembic 增量升级，修改模型前应规划迁移。

环境变量见 `.env.example`：COMPOSE_PROJECT_NAME 隔离栈名；FRONTEND_PORT/BACKEND_PORT/DB_PORT 映射端口；POSTGRES_DB/USER/PASSWORD 配置库；JWT_SECRET 签名；SEED_DEMO 控制启动 seed。Compose 恰好 frontend/backend/worker/db/redis 5 个服务，全具健康检查，worker 使用定向 Celery ping。db-data、redis-data 与 artifacts 命名卷分别持久化库、队列、计算 JSON；API 与 worker 共享 artifacts。Nginx `/api/` 剥离前缀，API 原生路由不带 `/api`。

请求 ID 与全局错误两个中间件输出可追踪错误；数据库审计记录登录、导入、入队、完成及审核。所有 SQL 通过 ORM 绑定。CSV 字段对公式前缀转义。JWT 密钥及数据库口令为本地演示值；部署前应通过环境变量替换。

共享枚举：后端 `backend/src/constants/enums.py` 的 Role、RunStatus、ProposalStatus；前端 `frontend/src/constants/enums.ts` 同组角色和状态标签；使用处为 dependencies、运行/提案 service、Badge、Layout、各页面。数据库以字符串存储，schema 使用受限状态或权限检查，不接受任意审核状态。

测试脚本、真实截图与结果全部位于批次根目录 `test-artifacts/gb-0003/`，源码中不放测试报告和日志。收尾：`docker compose down -v --remove-orphans` 会删除本栈演示数据卷。

## 已完成的本地验收

本批次已实际构建并验证5/5服务healthy、seed连续两次幂等且保留用户修改、35项API与权限检查、Celery创建→计算→提案→审核→CSV闭环。Playwright又从界面建立新研究并审核，保留8张1440×900截图和1024/390宽度响应式证据；Lead用内置浏览器复查了400篮子/52频繁项集/65规则的真实结果。详情和已知差异见批次根 `test-artifacts/gb-0003/TESTING.md`。

初次真机启动发现Celery5.4自动拉到的新Kombu5.7要求redis-py≥6.1，而Celery5.4 Redis extra限制redis<6，worker真实退出；现将Kombu锁定5.4.2并重新跑通任务。Nginx健康探针使用127.0.0.1，避免BusyBox wget优先IPv6 localhost而误报不健康。Vite锁定6.4.6并重新构建，当次npm audit结果为0。

## License

MIT，见 LICENSE。
