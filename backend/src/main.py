import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from redis import Redis
from src.config.database import Base,engine,SessionLocal
from src.config.settings import SEED_DEMO,REDIS_URL
from src.models import *
from src.middlewares.request_id import RequestIDMiddleware
from src.middlewares.errors import ErrorMiddleware
from src.routes import auth,catalog,research,audit


def _ensure_schema():
    """轻量幂等迁移：为已存在的库补齐后续新增列（新库由 metadata 直接建出）。"""
    with engine.begin() as conn:
        tables = {r[0] for r in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name='rule_runs'"))}
        if 'rule_runs' not in tables:
            return
        cols = {r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='rule_runs'"))}
        if 'attempts' not in cols:
            conn.execute(text(
                "ALTER TABLE rule_runs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"))


@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 _ensure_schema()
 if SEED_DEMO:
  try:
   from scripts.seed_demo import seed
   seed()
  except Exception: logging.exception('Seed failed; API startup continues')
 # 对账放在 seed 之后：清理孤儿临时结果文件，并为所有历史成功研究（含 seed 基准）
 # 补齐/修复结果文件，保证启动后页面、规则下载与结果文件即对应同一份完整结果
 try:
  from src.services.artifacts import reconcile
  with SessionLocal() as db:
   summary=reconcile(db)
  logging.getLogger('gucang').info('结果文件对账完成 %s',summary)
 except Exception: logging.exception('结果文件对账失败；服务继续启动')
 yield
app=FastAPI(title='谷仓组合选品研究室',lifespan=lifespan)
app.add_middleware(ErrorMiddleware);app.add_middleware(RequestIDMiddleware)
for r in (auth,catalog,research,audit): app.include_router(r.router)
@app.get('/health')
def health():
 with engine.connect() as c: c.execute(text('select 1'))
 Redis.from_url(REDIS_URL).ping()
 return {'status':'ok'}
