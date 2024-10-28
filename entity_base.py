import logging
from typing import Any, Type, TypeVar, Callable, Self

from sqlalchemy import Column
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from pydantic import BaseModel

EntityType = TypeVar('EntityType', bound="EntityMixin")
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class EntityMixin:
    __abstract__ = True

    @staticmethod
    def _error_handler(
        detail: str,
        raise_if_error: bool = True,
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs) -> Any:
                session: Session = kwargs.get("session") or args[1] if len(args) > 1 else None
                if not session:
                    raise ValueError("Session is required for this operation")

                try:
                    return func(*args, **kwargs)
                except SQLAlchemyError as e:
                    error_detail = f"{detail}: {e}"
                    logger.error(error_detail)
                    session.rollback()
                    if raise_if_error:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=error_detail,
                        )
                    return None
            return wrapper
        return decorator

    @classmethod
    @_error_handler(detail="Error finding entity by ID")
    def findById(
        cls: Type[EntityType],
        session: Session,
        id: Any,
        raise_if_not_found: bool = True,
    ) -> EntityType | int:
        entity = session.query(cls).filter(cls.id == id).first()
        logger.debug(f"{cls.__name__} found by ID {id}: {entity}")
        if raise_if_not_found and not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} not found with ID {id}",
            )
        return entity

    @classmethod
    @_error_handler(detail="Error finding all entities")
    def findAll(
        cls: Type[EntityType],
        session: Session,
        offset: int = 0,
        limit: int = 100,
    ) -> list[EntityType]:
        entities = session.query(cls).offset(offset).limit(limit).all()
        logger.debug(f"Entities found with offset {offset} and limit {limit}: {entities}")
        return entities

    @classmethod
    @_error_handler(detail="Error finding entity by filters")
    def findBy(
        cls: Type[EntityType],
        session: Session,
        raise_if_not_found: bool = True,
        return_as_list: bool = False,
        **filters: Any,
    ) -> EntityType | list[EntityType] | None:

        entities = session.query(cls).filter_by(**filters).all()
        logger.debug(f"{cls.__name__} found with filters {filters}: {entities}")
        if len(entities) > 1:
            return entities

        if raise_if_not_found and not entities:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} not found",
            )

        if return_as_list:
            return entities
        else:
            return entities[0] if entities else None

    @classmethod
    @_error_handler(detail="Error deleting entity by ID")
    def deleteById(
        cls: Type[EntityType],
        session: Session,
        id: Any,
        raise_if_not_found: bool = True,
    ) -> bool:
        entity = session.query(cls).filter(cls.id == id).first()
        if raise_if_not_found and not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} not found with ID {id}",
            )
        if entity:
            logger.debug(f"Deleting {cls.__name__} by ID {id}: {entity}")
            session.delete(entity)
            session.commit()
            logger.info(f"{cls.__name__} deleted by ID {id}")
            return True

        logger.warning(f"{cls.__name__} not found by ID {id}, skip deletion")
        return False

    @classmethod
    @_error_handler(detail="Error deleting entities by filters")
    def deleteBy(
        cls: Type[EntityType],
        session: Session,
        raise_if_not_found: bool = True,
        **wheres: Any,
    ) -> int:

        entities = session.query(cls).filter_by(**wheres).all()
        logger.debug(f"{cls.__name__} found with filters {wheres}: {entities}")
        if raise_if_not_found and not entities:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{cls.__name__} not found",
            )

        for entity in entities:
            session.delete(entity)

        session.commit()
        logger.info(f"{cls.__name__} deleted with filters {wheres}")
        return len(entities)

    @classmethod
    @_error_handler(detail="Error checking existence of entity")
    def exists(
        cls: Type[EntityType],
        session: Session,
        should_exist: bool,
        field: str,
        value: Any,
        field_name: str = None,
        raise_error: bool = True,
    ) -> int:

        entity = session.query(cls).filter_by(**{field: value}).first()
        detail = f"{cls.__name__} with {field_name if field_name else field.replace('_', ' ')} {value}"
        if should_exist and entity:
            detail += " already exists"
            logger.info(detail)
            if raise_error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=detail,
                )
            return 1

        elif not should_exist and not entity:
            detail += " not found"
            logger.info(detail)
            if raise_error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=detail,
                )
            return 2

        return 0

    @classmethod
    @_error_handler(detail="Error checking existence of entity")
    def conflict(
        cls: Type[EntityType],
        session: Session,
        id: Any,
        field: str,
        value: Any,
        field_name: str = None,
        raise_error: bool = True,
    ) -> bool:

        detail = f"{cls.__name__} with {field_name if field_name else field.replace('_', ' ')}={value} and different ID"
        entities = session.query(cls).filter_by(**{field: value})
        for entity in entities:
            if entity.id != id:
                detail = f"{detail} {entity.id} found"
                logger.info(detail)
                if raise_error:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=detail,
                    )
                return True

        return False


    @_error_handler(detail="Error saving entity")
    def save(
        self,
        session: Session,
    ) -> Self:
        logger.debug(f"Saving {self.__class__.__name__}: {self}")
        if not session.object_session(self):
            logger.debug(f"{self} is not part of the session, adding it.")
            session.add(self)
        else:
            logger.debug(f"{self} is already part of the session, skipping add.")

        session.commit()
        session.refresh(self)
        logger.info(f"{self.__class__.__name__} saved: {self}")
        return self

    @_error_handler(detail="Error updating entity")
    def update(
        self,
        session: Session,
        data_to_update: BaseModel | dict,
        excluded_fields: list[str] = None,
        strict_mode: bool = False,
    ) -> Self:

        if excluded_fields is None:
            excluded_fields = []  # type: ignore

        if isinstance(data_to_update, BaseModel):
            data_to_update = data_to_update.model_dump()

        for excluded in excluded_fields:
            if data_to_update.get(excluded) is not None:
                try:
                    data_to_update.pop(excluded)
                except KeyError as e:
                    detail = f"There is not such key '{excluded}', continuing"
                    logger.warning(detail)
                    if strict_mode:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=detail,
                        )
                    continue

        for key, value in data_to_update.items():
            logger.debug(f"Updating {self.__class__.__name__}.{key} = {value}")
            if key not in self.__table__.columns:
                detail = f"{self.__class__.__name__} does not have field '{key}'"
                logger.error(detail)
                if strict_mode:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=detail,
                    )
                continue

            column: Column = self.__table__.columns[key]
            expected_type = column.type.python_type

            if column.nullable and value is None:
                continue

            if not isinstance(value, expected_type):
                detail = f"Invalid type for field '{self.__class__.__name__}.{key}': " + \
                    f"expected {expected_type}, got {type(value)}"
                logger.error(detail)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=detail,
                )
            setattr(self, key, value)

        return self.save(session)

    @_error_handler(detail="Error deleting entity")
    def delete(
        self,
        session: Session,
    ) -> bool:
        session.delete(self)
        session.commit()
        logger.info(f"{self.__class__.__name__} deleted: {self}")
        return True


    def __str__(self) -> str:
        class_name = type(self).__name__
        attributes = ', '.join(f"{attr}={getattr(self, attr)}" for attr in self.__dict__)
        return f"{class_name}({attributes})"

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> dict[str, Any]:
        entity_dict = {}
        for column in self.__table__.columns:
            entity_dict[column.name] = getattr(self, column.name)
        return entity_dict
