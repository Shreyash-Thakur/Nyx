import math
import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id: uuid.UUID) -> ModelT | None:
        return self.db.get(self.model, id)

    def get_or_raise(self, id: uuid.UUID) -> ModelT:
        obj = self.get(id)
        if obj is None:
            raise ValueError(f"{self.model.__name__} {id} not found")
        return obj

    def list(self, *, limit: int = 20, offset: int = 0) -> list[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def count(self, *filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        return self.db.scalar(stmt) or 0

    def save(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
