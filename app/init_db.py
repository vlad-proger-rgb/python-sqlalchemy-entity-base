import random
import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Note


async def init_db(db: AsyncSession) -> None:
    colors = ["red", "green", "blue", "yellow", "purple", "orange", "pink"]
    created_at = dt.datetime.now()

    for i in range(100):
        created_at += dt.timedelta(hours=0.5)
        await Note(
            title=f"Title {i+1}",
            content=f"Content {i+1}",
            color=random.choice(colors),
            created_at=created_at,
        ).save(db)

