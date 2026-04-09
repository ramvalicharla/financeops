from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from financeops.core.exceptions import ValidationError


@dataclass(frozen=True)
class MutationContext:
    intent_id: uuid.UUID
    job_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_role: str | None
    intent_type: str


_current_mutation_context: ContextVar[MutationContext | None] = ContextVar(
    "financeops_mutation_context",
    default=None,
)


@contextmanager
def governed_mutation_context(context: MutationContext):
    token = _current_mutation_context.set(context)
    try:
        yield context
    finally:
        _current_mutation_context.reset(token)


def get_mutation_context() -> MutationContext | None:
    return _current_mutation_context.get()


def require_mutation_context(operation: str) -> MutationContext:
    context = get_mutation_context()
    if context is None:
        raise ValidationError(
            f"{operation} is governed by the intent pipeline and cannot run without an active intent/job context."
        )
    return context


def apply_mutation_linkage(record: Any) -> Any:
    context = require_mutation_context("Governed financial mutation")
    if hasattr(record, "created_by_intent_id") and getattr(record, "created_by_intent_id", None) is None:
        setattr(record, "created_by_intent_id", context.intent_id)
    if hasattr(record, "recorded_by_job_id"):
        setattr(record, "recorded_by_job_id", context.job_id)
    return record
