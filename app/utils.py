from typing import Union

from fastapi import Request, Query, Body
from pydantic import BaseModel, ConfigDict, create_model

from app.database import async_session
from app.schemas import Pagination, Filter, Range
from app.enums import SortEnum


async def get_db():
    async with async_session() as session:
        yield session


def pagination_params(
    request: Request,
    page: int = Query(1, description="Page number", ge=1),
    per_page: int = Query(10, description="Items per page", ge=1, le=100, alias="perPage"),
    order: SortEnum = Query(SortEnum.ASC, description="Order: 'asc' or 'desc'"),
    sort_by: str = Query("id", description="Field to sort by", alias="sortBy"),
    to_include: list[str] = Query(None, description="Fields to include"),
    filters: list[Filter | Range] = Body(None, description="Filters to search by"),
) -> Pagination:
    print(f"UTILS pagination_params {page=}, {per_page=}, {order=}, {sort_by=}, {to_include=}, {filters=}")

    return Pagination(
        page=page,
        per_page=per_page,
        order=order,
        sort_by=sort_by,
        to_include=to_include or [],
        filters=filters or [],
        url=str(request.url),
    )


def make_optional_schema(base_model: type[BaseModel]) -> type[BaseModel]:
    """Create a new schema with all fields optional from the given base model."""
    optional_fields = {
        field_name: (Union[field.annotation, None], None)
        for field_name, field in base_model.model_fields.items()
    }
    return create_model(
        f"Optional{base_model.__name__}",
        __config__=ConfigDict(from_attributes=True),
        **optional_fields
    )  # type: ignore


