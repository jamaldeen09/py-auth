import pytest_asyncio, os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import event
from py_auth_sqlalchemy import SqlAlchemyAdapter
from dotenv import load_dotenv, find_dotenv

from .models import Base, Session, User, Account
load_dotenv(find_dotenv())

@pytest_asyncio.fixture(scope="session")
async def engine():
    database_url = os.getenv("TEST_DATABASE_URL")
    engine = create_async_engine(
        database_url,
        echo=True,
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture(autouse=True)
async def clean_database(engine):
    yield

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

@pytest_asyncio.fixture
async def adapter(engine):
    return SqlAlchemyAdapter(
        engine,
        session_model=Session,
        user_model=User,
        account_model=Account,
    )