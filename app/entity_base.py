import sys
import logging
import traceback

from typing import Self, Sequence, Iterable
from collections.abc import Callable
from functools import wraps
from uuid import UUID, uuid4
from yarl import URL
from math import ceil

from sqlalchemy import Integer, select, desc, asc, func
from sqlalchemy.orm import Load, Mapped, mapped_column
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from pydantic import BaseModel

from .database import Base
from .schemas import Pagination, PaginationMeta, Filter, Range
from .enums import SortEnum
from .utils import make_optional_schema


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class EntityPagination:

    def __init__(
        self,
        entities: Sequence["EntityMixin"],
        pgn: Pagination,
        pydantic_response_model: type[BaseModel] | None = None,
        total_count: int | None = None,
    ) -> None:
        print(f"PAGINATION {entities=}, {pgn=}, {pydantic_response_model=}, {total_count=}")
        self.entities = entities
        self.pgn = pgn
        self.total_count = total_count

        if pydantic_response_model:
            self.response_model = pydantic_response_model

    def _modify_page(self, url: str, page: int) -> str:
        parsed_url = URL(url)
        return str(parsed_url.update_query(page=page))

    def ids(self) -> list[object]:
        return [entity.id for entity in self.entities]

    @property
    def entity_name(self) -> str:
        return self.entities[0].__class__.__name__ if self.entities else ""

    @property
    def total_pages(self) -> int:
        return ceil(self.total_count / self.pgn.per_page)

    @property
    def prev(self) -> str | None:
        return (
            self._modify_page(self.pgn.url, self.pgn.page - 1)
            if self.pgn.page > 1 else None
        )

    @property
    def next(self) -> str | None:
        return (
            self._modify_page(self.pgn.url, self.pgn.page + 1)
            if self.total_count > self.pgn.page * self.pgn.per_page else None
        )

    @property
    def meta(self) -> PaginationMeta:
        return PaginationMeta(
            total=self.total_count,
            total_pages=self.total_pages,
            page=self.pgn.page,
            per_page=self.pgn.per_page,
            prev=self.prev,
            next=self.next,
        )

    def __iter__(self) -> Iterable["EntityMixin"]:
        return iter(self.entities)

    def __getitem__(self, index: int) -> "EntityMixin":
        return self.entities[index]

    def __len__(self) -> int:
        return len(self.entities)

    # def get(self) -> Sequence["EntityMixin"] | list[dict[str, object]]:
    #     if self.pgn.to_include:
    #         return [{field: getattr(entity, field, None) for field in self.pgn.to_include}
    #                 for entity in self.entities]
    #     return self.entities

    def get_raw(self) -> Sequence["EntityMixin"]:
        return self.entities

    def get(self) -> list[BaseModel]:
        if self.response_model:
            return [make_optional_schema(self.response_model).model_validate(entity)
                    for entity in self.entities]

        return [entity.pydantic_response_model.model_validate(entity)
                for entity in self.entities]


class EntityMixin(Base):
    __abstract__ = True
    pydantic_response_model: type[BaseModel]
    # id: Mapped[UUID] = mapped_column(primary_key=True, unique=True, nullable=False, default=uuid4)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False, autoincrement=True)

    @classmethod
    def _compose_error_message(cls, detail: str, func: Callable, args: tuple, kwargs: dict, e: Exception, traceback: str) -> str:
        return f"{detail}: {e} - Func: {func.__name__}, Args: {args}, Kwargs: {kwargs}, Exception Type: {type(e).__name__} - Traceback: {traceback}"

    @staticmethod
    def _error_handler(
        detail: str,
        raise_if_error: bool = True,
    ) -> Callable:

        def decorator(func: Callable) -> Callable:

            @wraps(func)
            async def wrapper(*args, **kwargs) -> object:
                session: AsyncSession = kwargs.get("session") or args[1] if len(args) > 1 else None
                if not session:
                    raise ValueError("AsyncSession is required for this operation")

                try:
                    return await func(*args, **kwargs)
                except SQLAlchemyError as e:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    formatted_traceback = '\n'.join(traceback.format_exception(exc_type, exc_value, exc_tb))
                    logger.error(EntityMixin._compose_error_message(detail, func, args, kwargs, e, formatted_traceback))
                    await session.rollback()
                    if raise_if_error:
                        raise HTTPException(500, "Database error")
                except HTTPException as e:
                    raise
                except Exception as e:
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    formatted_traceback = '\n'.join(traceback.format_exception(exc_type, exc_value, exc_tb))
                    logger.error(EntityMixin._compose_error_message(detail, func, args, kwargs, e, formatted_traceback))
                    if raise_if_error:
                        raise HTTPException(500, "Internal server error")

                return None

            return wrapper
        return decorator


    @classmethod
    def _is_valid_field(cls, field: str) -> bool:
        return field in cls.__table__.columns

    @classmethod
    def _validate_field(cls, field: str) -> None:
        if not cls._is_valid_field(field):
            raise HTTPException(400, f"Invalid field for {cls.__name__}: {field}")

    @classmethod
    def _validate_pgn(cls, pgn: Pagination) -> None:
        fields_to_check = [pgn.sort_by] + \
                        [f.key for f in pgn.filters if isinstance(f, Filter)] + \
                        [f.field for f in pgn.filters if isinstance(f, Range)] + \
                        pgn.to_include

        for field in fields_to_check:
            cls._validate_field(field)

    # @classmethod
    # @_error_handler(detail="Error finding entities")
    # async def findBy(
    #     cls,
    #     session: AsyncSession,
    #     raise_if_not_found: bool = True,
    #     return_first: bool = False,
    #     pgn: Pagination | None = None,
    #     load_options: list[Load] | None = None,
    #     **filters: object,
    # ) -> Self | Sequence[Self] | EntityPagination | None:
    #     if pgn:
    #         cls._validate_pgn(pgn)

        # if pgn.to_include:
        #     selected_columns = [getattr(cls, field) for field in pgn.to_include]
        # else:
        #     selected_columns = [cls]

    #     stmt = select(*selected_columns).filter_by(**filters)
    #     if load_options:
    #         stmt = stmt.options(*load_options)

    #     if pgn:
    #         for filter in pgn.filters:
    #             logger.debug(f"{filter=} {type(filter)=}")
    #             if isinstance(filter, Filter):
    #                 stmt = stmt.filter(getattr(cls, filter.key) == filter.value)
    #             elif isinstance(filter, Range):
    #                 if filter.start:
    #                     stmt = stmt.filter(getattr(cls, filter.field) >= filter.start)
    #                 if filter.end:
    #                     stmt = stmt.filter(getattr(cls, filter.field) <= filter.end)

    #         order = desc if pgn.order == SortEnum.DESC else asc
    #         stmt = (
    #             stmt.offset(
    #                 pgn.page - 1
    #                 if pgn.page == 1
    #                 else (pgn.page - 1) * pgn.per_page
    #             )
    #             .limit(pgn.per_page)
    #             .order_by(order(getattr(cls, pgn.sort_by)))
    #         )

    #         count_stmt = select(func.count(cls.id)).filter_by(**filters)
    #         for filter in pgn.filters:
    #             if isinstance(filter, Filter):
    #                 count_stmt = count_stmt.filter(getattr(cls, filter.key) == filter.value)
    #             elif isinstance(filter, Range):
    #                 if filter.start:
    #                     count_stmt = count_stmt.filter(getattr(cls, filter.field) >= filter.start)
    #                 if filter.end:
    #                     count_stmt = count_stmt.filter(getattr(cls, filter.field) <= filter.end)

    #         count_result = await session.scalars(count_stmt)
    #         total_count = count_result.first()

    #         result = await session.scalars(stmt)
    #         entities = result.all()

    #         logger.debug(f"{cls.__name__} entities found with {pgn=}: {entities}")
    #         if not entities and raise_if_not_found:
    #             raise HTTPException(404, f"{cls.__name__} not found with {pgn=}")

    #         if return_first:
    #             return entities[0] if entities else None
    #         return EntityPagination(entities, pgn, total_count)

    #     result = await session.scalars(stmt)
    #     entities = result.all()

    #     logger.debug(f"{cls.__name__} entities found with {pgn=}: {entities}")
    #     if not entities and raise_if_not_found:
    #         raise HTTPException(404, f"{cls.__name__} not found with {pgn=}")

    #     if return_first:
    #         return entities[0] if entities else None

    #     return entities

    @classmethod
    @_error_handler(detail="Error finding entities")
    async def findBy(
        cls,
        session: AsyncSession,
        raise_if_not_found: bool = True,
        return_first: bool = False,
        pgn: Pagination | None = None,
        load_options: list[Load] | None = None,
        **filters: object,
    ) -> Self | Sequence[Self] | EntityPagination | None:
        if pgn:
            cls._validate_pgn(pgn)

        stmt = cls._build_query(filters, load_options, pgn)
        stmt = cls._apply_filters(stmt, pgn)
        if pgn:
            stmt, count_stmt = cls._apply_pagination(stmt, pgn, filters)

        result = await session.scalars(stmt)
        entities = result.all()

        if not entities and raise_if_not_found:
            raise HTTPException(404, f"{cls.__name__} not found with given parameters")

        if return_first:
            return entities[0] if entities else None

        if pgn:
            total_count = await cls._get_total_count(session, count_stmt)
            return EntityPagination(entities, pgn, cls.pydantic_response_model, total_count)

        return entities

    @classmethod
    def _build_query(
        cls,
        filters: dict,
        load_options: list[Load] | None,
        pgn: Pagination | None = None,
    ) -> Select:
        if pgn and pgn.to_include:
            selected_columns = [getattr(cls, field) for field in pgn.to_include]
        else:
            selected_columns = [cls]

        stmt = select(*selected_columns)
        if filters:
            stmt = stmt.filter_by(**filters)
        if load_options:
            stmt = stmt.options(*load_options)
        return stmt

    @classmethod
    def _apply_filters(
        cls, stmt: Select, pgn: Pagination | None
    ) -> Select:
        if not pgn:
            return stmt

        for filter in pgn.filters:
            if isinstance(filter, Filter):
                stmt = stmt.filter(getattr(cls, filter.key) == filter.value)
            elif isinstance(filter, Range):
                if filter.start:
                    stmt = stmt.filter(getattr(cls, filter.field) >= filter.start)
                if filter.end:
                    stmt = stmt.filter(getattr(cls, filter.field) <= filter.end)

        return stmt

    @classmethod
    def _apply_pagination(
        cls, stmt: Select, pgn: Pagination, filters: dict
    ) -> tuple[Select, Select]:
        order = desc if pgn.order == SortEnum.DESC else asc
        stmt = (
            stmt.offset((pgn.page - 1) * pgn.per_page)
            .limit(pgn.per_page)
            .order_by(order(getattr(cls, pgn.sort_by)))
        )

        count_stmt = select(func.count(cls.id)).filter_by(**filters)
        for filter in pgn.filters:
            if isinstance(filter, Filter):
                count_stmt = count_stmt.filter(getattr(cls, filter.key) == filter.value)
            elif isinstance(filter, Range):
                if filter.start:
                    count_stmt = count_stmt.filter(getattr(cls, filter.field) >= filter.start)
                if filter.end:
                    count_stmt = count_stmt.filter(getattr(cls, filter.field) <= filter.end)

        return stmt, count_stmt

    @classmethod
    async def _get_total_count(cls, session: AsyncSession, count_stmt: Select) -> int:
        result = await session.scalars(count_stmt)
        return result.first() or 0

    @classmethod
    @_error_handler(detail="Error finding entity by ID")
    async def findById(
        cls,
        session: AsyncSession,
        id: object,
        raise_if_not_found: bool = True,
        load_options: list[Load] | None = None,
    ) -> Self | None:
        return await cls.findBy(
            session,
            raise_if_not_found,
            True,
            load_options=load_options,
            id=id,
        )

    @classmethod
    @_error_handler(detail="Error finding entity")
    async def findOne(
        cls,
        session: AsyncSession,
        raise_if_not_found: bool = True,
        load_options: list[Load] | None = None,
        **filters: object,
    ) -> Self | None:
        return await cls.findBy(
            session,
            raise_if_not_found,
            True,
            load_options=load_options,
            **filters,
        )

    @classmethod
    @_error_handler(detail="Error finding entities")
    async def findAll(
        cls,
        session: AsyncSession,
        pgn: Pagination | None = None,
        **filters: object,
    ) -> EntityPagination | Sequence[Self]:
        return await cls.findBy(session, False, False, pgn, **filters)


    @classmethod
    @_error_handler(detail="Error deleting entity by ID")
    async def deleteById(
        cls,
        session: AsyncSession,
        id: object,
        raise_if_not_found: bool = True,
    ) -> bool:
        entity = await cls.findById(session, id, raise_if_not_found=raise_if_not_found)
        if entity:
            await session.delete(entity)
            await session.commit()
            logger.info(f"{cls.__name__} deleted by ID {id}")
            return True
        return False

    @classmethod
    @_error_handler(detail="Error deleting entities by filters")
    async def deleteBy(
        cls,
        session: AsyncSession,
        raise_if_not_found: bool = True,
        **filters: object,
    ) -> int:
        entities = await cls.findBy(session, raise_if_not_found=raise_if_not_found, **filters)
        if entities:
            for entity in entities if isinstance(entities, list) else [entities]:
                await session.delete(entity)
            await session.commit()
            logger.info(f"{cls.__name__} deleted with filters {filters}")
            return len(entities) if isinstance(entities, list) else 1
        return 0

    @classmethod
    @_error_handler(detail="Error checking existence of entity")
    async def exists(
        cls,
        session: AsyncSession,
        should_exist: bool,
        field: str,
        value: object,
        field_name: str | None = None,
        raise_error: bool = True,
    ) -> int:
        result = await session.scalars(select(cls).filter_by(**{field: value}))
        entity = result.first()
        detail = f"{cls.__name__} with {field_name if field_name else field.replace('_', ' ')} {value}"
        if should_exist and entity:
            detail += " already exists"
            logger.info(detail)
            if raise_error:
                raise HTTPException(409, detail)
            return 1

        elif not should_exist and not entity:
            detail += " not found"
            logger.info(detail)
            if raise_error:
                raise HTTPException(404, detail)
            return 2

        return 0

    @classmethod
    @_error_handler(detail="Error checking existence of entity")
    async def conflict(
        cls,
        session: AsyncSession,
        id: object,
        field: str,
        value: object,
        field_name: str | None = None,
        raise_error: bool = True,
    ) -> bool:
        detail = f"{cls.__name__} with {field_name if field_name else field.replace('_', ' ')}={value} and different ID"
        result = await session.scalars(select(cls).filter_by(**{field: value}))
        for entity in result.all():
            if entity.id != id:
                detail = f"{detail} {entity.id} found"
                logger.info(detail)
                if raise_error:
                    raise HTTPException(409, detail)
                return True

        return False


    @_error_handler(detail="Error saving entity")
    async def save(
        self,
        session: AsyncSession,
    ) -> Self:
        logger.debug(f"Saving entity: {self}")
        session.add(self)
        await session.commit()
        await session.refresh(self)
        logger.info(f"Entity saved: {self}")
        return self


    def _validate_fields(self, updates: dict, strict: bool = False) -> dict:
        for key in updates:
            if not hasattr(self, key):
                updates.pop(key)
                if strict:
                    raise HTTPException(400, f"Invalid field {key} for {type(self).__name__}")

        if not any(getattr(self, key) != value for key, value in updates.items()):
            raise HTTPException(304, "No changes were made")

        return updates

    @_error_handler(detail="Error updating entity")
    async def update(
        self,
        session: AsyncSession,
        updates: BaseModel | dict,
        exclude: list[str] | None = None,
    ) -> Self:
        if exclude is None:
            exclude = []

        updates = updates.model_dump(exclude_unset=True) if isinstance(updates, BaseModel) else updates
        for key in exclude:
            updates.pop(key, None)

        updates = self._validate_fields(updates)
        for key, value in updates.items():
            setattr(self, key, value)

        return await self.save(session)

    @_error_handler(detail="Error deleting entity")
    async def delete(
        self,
        session: AsyncSession,
    ) -> bool:
        await session.delete(self)
        await session.commit()
        logger.info(f"{self.__class__.__name__} deleted: {self}")
        return True


    def __str__(self) -> str:
        return f"{type(self).__name__}({', '.join(f'{k}={v}' for k, v in self.__dict__.items() if not k.startswith('_'))})"

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(f'{k}={repr(v)}' for k, v in self.__dict__.items() if not k.startswith('_'))})"

    def to_dict(self) -> dict[str, object]:
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}
