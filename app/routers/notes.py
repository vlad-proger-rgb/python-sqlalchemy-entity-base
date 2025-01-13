from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note
from app.utils import get_db, pagination_params
from app.schemas import (
    Msg,
    MsgPGN,
    Pagination as PGN,
    Note as N,
    NoteInDB as NinDB,
)


router = APIRouter()


@router.post("/notes/all", response_model=MsgPGN[list[NinDB]])
async def get_notes(
    db: Annotated[AsyncSession, Depends(get_db)],
    pgn: Annotated[PGN, Depends(pagination_params)],
) -> MsgPGN[list[NinDB]]:
    notes = await Note.findAll(db, pgn)
    return MsgPGN(
        code=200,
        msg="Notes were retrieved",
        data=notes.get(),
        pgn=notes.meta,
    )

@router.get("/notes/{note_id}", response_model=Msg[NinDB])
async def get_note(
    db: Annotated[AsyncSession, Depends(get_db)],
    note_id: int,
) -> Msg[NinDB]:
    note = await Note.findById(db, note_id)
    return Msg(
        code=200,
        msg="Note was retrieved",
        data=note,
    )

@router.post("/notes", response_model=Msg[int])
async def create_note(
    db: Annotated[AsyncSession, Depends(get_db)],
    note: N,
) -> Msg[int]:
    new_note = await Note(title=note.title, content=note.content).save(db)
    return Msg(
        code=201,
        msg="Note was created",
        data=new_note.id,
    )

@router.put("/notes/{note_id}", response_model=Msg[UUID])
async def update_note(
    db: Annotated[AsyncSession, Depends(get_db)],
    note_id: UUID,
    new_note: N,
) -> Msg[int]:
    note = await Note.findById(db, note_id)
    await note.update(new_note)
    return Msg(
        code=200,
        msg="Note was updated",
        data=note.id,
    )

@router.delete("/notes/{note_id}", response_model=Msg[None])
async def delete_note(
    db: Annotated[AsyncSession, Depends(get_db)],
    note_id: int,
) -> Msg[None]:
    await Note.deleteById(db, note_id)
    return Msg(
        code=200,
        msg="Note was deleted",
    )

