from collections.abc import AsyncGenerator, Generator
from os import getenv

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_SYNC_URL = getenv("DATABASE_SYNC_URL")
DATABASE_ASYNC_URL = getenv("DATABASE_ASYNC_URL")

if not DATABASE_SYNC_URL:
    raise RuntimeError("DATABASE_SYNC_URL is not set")

if not DATABASE_ASYNC_URL:
    raise RuntimeError("DATABASE_ASYNC_URL is not set")

sync_engine = create_engine(DATABASE_SYNC_URL, pool_pre_ping=True)
async_engine = create_async_engine(DATABASE_ASYNC_URL, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


def get_sync_session() -> Generator[Session, None, None]:
    with SyncSessionLocal() as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
