from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import httpx


@dataclass(slots=True)
class SmokeCheck:
    name: str
    method: str
    path: str
    expected_statuses: set[int]
    protected: bool = False
    params: dict[str, Any] | None = None
    json_body: dict[str, Any] | None = None


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _base_url() -> str:
    base = _env("BASE_URL")
    if not base:
        raise RuntimeError("BASE_URL is required")
    return base if base.endswith("/") else f"{base}/"


async def _login_for_token(client: httpx.AsyncClient, base_url: str) -> str | None:
    existing_token = _env("ACCESS_TOKEN")
    if existing_token:
        return existing_token

    email = _env("AUTH_EMAIL")
    password = _env("AUTH_PASSWORD")
    if not email or not password:
        return None

    url = urljoin(base_url, "api/v1/auth/login")
    response = await client.post(url, json={"email": email, "password": password})
    if response.status_code != 200:
        raise RuntimeError(f"auth/login failed: {response.status_code} {response.text[:300]}")
    payload = response.json()
    token = payload.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError("auth/login returned 200 but no access_token")
    return str(token)


async def _discover_entity_id(client: httpx.AsyncClient, base_url: str, token: str) -> str | None:
    response = await client.get(
        urljoin(base_url, "api/v1/org-setup/summary"),
        headers={"Authorization": f"Bearer {token}"},
    )
    if response.status_code != 200:
        return None
    payload = response.json().get("data", {})
    entities = payload.get("entities") or payload.get("org_entities") or []
    if not entities:
        return None
    first = entities[0] if isinstance(entities, list) else None
    if not isinstance(first, dict):
        return None
    raw_id = first.get("id") or first.get("org_entity_id") or first.get("entity_id")
    return str(raw_id) if raw_id else None


async def _run_check(
    client: httpx.AsyncClient,
    base_url: str,
    check: SmokeCheck,
    token: str | None,
) -> dict[str, Any]:
    if check.protected and not token:
        return {
            "name": check.name,
            "status": "skipped",
            "reason": "no ACCESS_TOKEN or AUTH_EMAIL/AUTH_PASSWORD provided",
            "path": check.path,
        }

    headers: dict[str, str] = {}
    if check.protected and token:
        headers["Authorization"] = f"Bearer {token}"

    url = urljoin(base_url, check.path.lstrip("/"))
    response = await client.request(
        check.method,
        url,
        headers=headers,
        params=check.params,
        json=check.json_body,
    )
    passed = response.status_code in check.expected_statuses
    return {
        "name": check.name,
        "status": "passed" if passed else "failed",
        "path": check.path,
        "method": check.method,
        "status_code": response.status_code,
        "expected_statuses": sorted(check.expected_statuses),
        "response_preview": response.text[:300],
    }


async def main() -> int:
    base_url = _base_url()
    timeout = float(_env("SMOKE_TIMEOUT_SECONDS", "15") or "15")
    today = date.today()
    month_ago = today - timedelta(days=30)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        token = await _login_for_token(client, base_url)
        entity_id = await _discover_entity_id(client, base_url, token) if token else None

        trial_balance_params = {
            "org_entity_id": entity_id,
            "as_of_date": today.isoformat(),
        } if entity_id else None
        pnl_params = {
            "org_entity_id": entity_id,
            "from_date": month_ago.isoformat(),
            "to_date": today.isoformat(),
        } if entity_id else None

        checks = [
            SmokeCheck("health", "GET", "/health", {200}),
            SmokeCheck("ready", "GET", "/ready", {200, 503}),
            SmokeCheck("auth_login_route", "POST", "/api/v1/auth/login", {200, 401, 422}, json_body={"email": "smoke@example.com", "password": "invalid"}),
            SmokeCheck("onboarding_summary", "GET", "/api/v1/org-setup/summary", {200}, protected=True),
            SmokeCheck("journal_list", "GET", "/api/v1/accounting/journals", {200}, protected=True),
            SmokeCheck(
                "journal_create_validation_path",
                "POST",
                "/api/v1/accounting/journals",
                {400, 401, 403, 422},
                protected=True,
                json_body={},
            ),
            SmokeCheck(
                "trial_balance",
                "GET",
                "/api/v1/accounting/trial-balance",
                {200, 422},
                protected=True,
                params=trial_balance_params,
            ),
            SmokeCheck(
                "pnl",
                "GET",
                "/api/v1/accounting/pnl",
                {200, 422},
                protected=True,
                params=pnl_params,
            ),
            SmokeCheck(
                "consolidation_summary",
                "GET",
                "/api/v1/consolidation/summary",
                {200, 422},
                protected=True,
            ),
            SmokeCheck("erp_sync_health", "GET", "/api/v1/erp-sync/health", {200}, protected=True),
            SmokeCheck("ai_anomalies", "GET", "/api/v1/ai/anomalies", {200}, protected=True),
        ]

        results = [await _run_check(client, base_url, item, token) for item in checks]

    failures = [item for item in results if item.get("status") == "failed"]
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "token_mode": "provided_or_logged_in" if token else "public_only",
        "entity_id_used": entity_id,
        "passed": len(failures) == 0,
        "failures": len(failures),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
