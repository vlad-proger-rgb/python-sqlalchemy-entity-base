from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.settings import DATABASE_URL


engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
)

class Base(DeclarativeBase):
    pass

async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
