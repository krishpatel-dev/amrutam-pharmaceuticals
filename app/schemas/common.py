"""Common/shared Pydantic schemas: pagination, success responses."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with shared config."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SuccessResponse(BaseSchema):
    """Standard success envelope."""

    success: bool = True
    message: str = "Operation completed successfully."
    data: Any = None


class PaginatedResponse(BaseSchema, Generic[T]):
    """Generic paginated response wrapper."""

    success: bool = True
    data: list[T]
    pagination: PaginationMeta


class PaginationMeta(BaseSchema):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, page: int, page_size: int, total: int) -> PaginationMeta:
        total_pages = max(1, -(-total // page_size))  # ceiling division
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ErrorDetail(BaseSchema):
    code: str
    message: str


class ErrorResponse(BaseSchema):
    success: bool = False
    error: ErrorDetail


class MessageResponse(BaseSchema):
    success: bool = True
    message: str
