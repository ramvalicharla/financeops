from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(page * page_size) < total,
            has_prev=page > 1,
        )


def clamp_pagination(page: int, page_size: int, max_page_size: int = 100) -> tuple[int, int]:
    """Clamp page and page_size to safe bounds. Returns (page, page_size)."""
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    return page, page_size


def calc_offset(page: int, page_size: int) -> int:
    """Calculate SQL OFFSET from 1-based page number."""
    return (page - 1) * page_size
