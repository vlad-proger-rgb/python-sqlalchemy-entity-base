import datetime as dt

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.entity_base import EntityMixin
from app.schemas import NoteInDB


class Note(EntityMixin):
    __tablename__ = "notes"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now())

    pydantic_response_model = NoteInDB
