from __future__ import annotations


def assert_deterministic_sorted(items: list[tuple]) -> None:
    if items != sorted(items):
        raise ValueError("items must be pre-sorted deterministically")
