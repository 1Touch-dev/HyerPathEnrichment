from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.session import init_db
from app.infrastructure.redis import close_redis, get_redis_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    get_redis_client()
    yield
    await close_redis()
