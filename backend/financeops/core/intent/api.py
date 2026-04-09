from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import Request

from financeops.core.intent.enums import IntentSourceChannel, IntentType
from financeops.core.intent.service import IntentActor
from financeops.db.models.users import IamUser


def build_idempotency_key(
    request: Request,
    *,
    intent_type: IntentType,
    actor: IamUser,
    body: Any | None = None,
    target_id: uuid.UUID | None = None,
) -> str:
    header_key = request.headers.get("Idempotency-Key")
    if header_key:
        return header_key
    body_payload = body.model_dump(mode="json") if hasattr(body, "model_dump") else body or {}
    fingerprint = {
        "intent_type": intent_type.value,
        "tenant_id": str(actor.tenant_id),
        "user_id": str(actor.id),
        "target_id": str(target_id) if target_id else "",
        "body": body_payload,
    }
    raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_intent_actor(request: Request, user: IamUser) -> IntentActor:
    return IntentActor(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role.value,
        source_channel=IntentSourceChannel.API.value,
        request_id=getattr(request.state, "request_id", None),
        correlation_id=str(getattr(request.state, "correlation_id", None) or "") or None,
    )
