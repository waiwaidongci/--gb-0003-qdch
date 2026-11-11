import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from redis import Redis
from src.config.database import Base,engine
from src.config.settings import SEED_DEMO,REDIS_URL
from src.models import *
from src.middlewares.request_id import RequestIDMiddleware
from src.middlewares.errors import ErrorMiddleware
from src.routes import auth,catalog,research,audit
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 if SEED_DEMO:
  try:
   from scripts.seed_demo import seed
   seed()
  except Exception: logging.exception('Seed failed; API startup continues')
 yield
app=FastAPI(title='谷仓组合选品研究室',lifespan=lifespan)
app.add_middleware(ErrorMiddleware);app.add_middleware(RequestIDMiddleware)
for r in (auth,catalog,research,audit): app.include_router(r.router)
@app.get('/health')
def health():
 with engine.connect() as c: c.execute(text('select 1'))
 Redis.from_url(REDIS_URL).ping()
 return {'status':'ok'}
