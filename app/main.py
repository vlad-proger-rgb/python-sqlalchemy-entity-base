from fastapi import FastAPI

from app.init_db import init_db
from app.database import Base, async_session, engine
from app.routers import (
    notes,
)

async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await init_db(session)
    yield

app = FastAPI(lifespan=lifespan)


app.include_router(notes.router)



