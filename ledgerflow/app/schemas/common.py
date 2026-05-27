from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def to_paginated(self, items: list[T], total: int) -> "PaginatedResponse[T]":
        import math
        return PaginatedResponse(
            items=items,
            total=total,
            page=self.page,
            page_size=self.page_size,
            pages=math.ceil(total / self.page_size) if total else 0,
        )


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class IDResponse(BaseModel):
    id: UUID
    message: str = "Created successfully"
