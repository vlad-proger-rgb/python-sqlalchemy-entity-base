import datetime as dt
from dateutil.parser import parse
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from app.enums import SortEnum


### General ###
class Msg[T](BaseModel):
    code: int | None = None
    msg: str | None = None
    data: T | None = None


### Pagination ###
class Filter(BaseModel):
    key: str
    value: object

class Range(BaseModel):
    field: str
    start: object
    end: object

    @field_validator("start", "end")
    def parse_value(cls, value):
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return parse(value)
            except ValueError:
                pass

        return value

class PaginationMeta(BaseModel):
    total: int
    total_pages: int
    page: int
    per_page: int
    prev: str | None
    next: str | None

class Pagination(BaseModel):
    page: int
    per_page: int
    order: SortEnum
    sort_by: str
    to_include: list[str]
    filters: list[Filter | Range]
    url: str

class MsgPGN[T](Msg[T]):
    pgn: PaginationMeta | None = None


### Note ###
class Note(BaseModel):
    title: str
    content: str
    color: str | None = None

class NoteInDB(Note):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: dt.datetime


