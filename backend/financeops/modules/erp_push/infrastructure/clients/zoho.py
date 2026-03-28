from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx

from financeops.modules.erp_push.domain.schemas import PushJournalPacket, PushResult
from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import (
    RateLimitError,
    TransientError,
    with_backoff,
)

ZOHO_API_BASE = "https://books.zoho.in/api/v3"

ZOHO_AUTH_INVALID_TOKEN = "ZOHO_AUTH_INVALID_TOKEN"
ZOHO_RATE_LIMIT = "ZOHO_RATE_LIMIT"
ZOHO_NETWORK = "ZOHO_NETWORK"
ZOHO_PAYLOAD_INVALID = "ZOHO_PAYLOAD_INVALID"


def _decimal_to_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _build_zoho_journal_payload(
    packet: PushJournalPacket,
    organization_id: str,
) -> dict[str, Any]:
    line_items: list[dict[str, Any]] = []
    for line in packet.lines:
        line_items.append(
            {
                "account_id": line.external_account_id,
                "description": line.narration or "",
                "debit_or_credit": "debit" if line.entry_type == "DEBIT" else "credit",
                "amount": _decimal_to_str(line.amount),
                "tax_id": line.tax_code or "",
            }
        )
    return {
        "organization_id": organization_id,
        "journal_date": packet.period_date,
        "reference_number": packet.reference or packet.jv_number,
        "notes": packet.description or "",
        "line_items": line_items,
    }


async def push_journal_to_zoho(
    packet: PushJournalPacket,
    *,
    access_token: str,
    organization_id: str,
    simulation: bool = False,
) -> PushResult:
    payload = _build_zoho_journal_payload(packet, organization_id)
    if simulation:
        return PushResult(
            success=True,
            external_journal_id=f"SIM-{packet.jv_number}",
            raw_response={"simulation": True, "payload": payload},
        )

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json",
    }
    params = {"organization_id": organization_id}
    url = f"{ZOHO_API_BASE}/journals"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await with_backoff(
                lambda: client.post(
                    url,
                    headers=headers,
                    params=params,
                    content=json.dumps(payload),
                ),
                context=f"ZOHO:push_journal:{packet.jv_id}",
            )
    except RateLimitError as exc:
        return PushResult(
            success=False,
            error_code=ZOHO_RATE_LIMIT,
            error_message=str(exc),
            error_category="SOFT",
        )
    except (TransientError, httpx.RequestError, httpx.TimeoutException) as exc:
        return PushResult(
            success=False,
            error_code=ZOHO_NETWORK,
            error_message=str(exc),
            error_category="SOFT",
        )

    if response.status_code == 401:
        return PushResult(
            success=False,
            error_code=ZOHO_AUTH_INVALID_TOKEN,
            error_message="Zoho access token invalid or expired",
            error_category="HARD",
        )
    if response.status_code in (400, 422):
        return PushResult(
            success=False,
            error_code=ZOHO_PAYLOAD_INVALID,
            error_message=f"Zoho rejected payload: {response.text[:300]}",
            error_category="HARD",
        )
    if response.status_code not in (200, 201):
        return PushResult(
            success=False,
            error_code=ZOHO_NETWORK,
            error_message=f"Unexpected status {response.status_code}",
            error_category="SOFT",
        )

    data = response.json()
    journal = data.get("journal", {}) if isinstance(data, dict) else {}
    journal_id = journal.get("journal_id") or data.get("journal_id", "")
    return PushResult(
        success=True,
        external_journal_id=str(journal_id),
        raw_response=data if isinstance(data, dict) else {},
    )


async def get_zoho_journal_status(
    external_journal_id: str,
    *,
    access_token: str,
    organization_id: str,
) -> dict[str, Any]:
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    params = {"organization_id": organization_id}
    url = f"{ZOHO_API_BASE}/journals/{external_journal_id}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await with_backoff(
            lambda: client.get(url, headers=headers, params=params),
            context=f"ZOHO:get_journal_status:{external_journal_id}",
            max_retries=3,
        )
    return {
        "found": response.status_code == 200,
        "status_code": response.status_code,
        "data": response.json() if response.status_code == 200 else {},
    }
