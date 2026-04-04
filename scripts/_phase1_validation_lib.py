from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ensure_artifacts_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return artifacts


def write_artifact(filename: str, payload: dict[str, Any]) -> Path:
    artifacts = ensure_artifacts_dir()
    path = artifacts / filename
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def required_env(name: str) -> str:
    value = env(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def base_url() -> str:
    value = required_env("BASE_URL")
    return value if value.endswith("/") else f"{value}/"


def _json_preview(payload: Any, limit: int = 1200) -> str:
    try:
        text = json.dumps(payload, default=str)
    except Exception:
        text = str(payload)
    return text[:limit]


def extract_enveloped_data(payload: Any) -> Any:
    if not isinstance(payload, dict):
        raise RuntimeError("response payload is not JSON object")
    if payload.get("success") is True:
        return payload.get("data")
    error = payload.get("error") or {}
    code = error.get("code") if isinstance(error, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    raise RuntimeError(f"API error: code={code} message={message}")


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout_seconds,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            payload = response.json()
        except Exception:
            payload = None
        return {
            "ok": True,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
            "payload": payload,
            "text_preview": response.text[:1200],
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "ok": False,
            "status_code": None,
            "elapsed_ms": elapsed_ms,
            "payload": None,
            "text_preview": "",
            "error": str(exc) or exc.__class__.__name__,
        }


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def issue_control_plane_token(
    *,
    secret_key: str,
    tenant_id: str,
    module_code: str = "validation",
    decision: str = "allow",
    ttl_minutes: int = 10,
) -> str:
    now = datetime.now(UTC)
    claims = {
        "tenant_id": tenant_id,
        "module_code": module_code,
        "decision": decision,
        "policy_snapshot_version": 1,
        "quota_check_id": str(uuid.uuid4()),
        "isolation_route_version": 1,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=ttl_minutes)).isoformat(),
        "correlation_id": str(uuid.uuid4()),
    }
    payload_json = json.dumps(claims, separators=(",", ":"), sort_keys=True)
    payload_segment = _b64url_encode(payload_json.encode("utf-8"))
    signature = hmac.new(
        secret_key.encode("utf-8"), payload_segment.encode("utf-8"), hashlib.sha256
    ).digest()
    return f"{payload_segment}.{_b64url_encode(signature)}"


def generate_totp(secret_base32: str, *, interval_seconds: int = 30, digits: int = 6) -> str:
    clean = secret_base32.strip().replace(" ", "").upper()
    key = base64.b32decode(clean, casefold=True)
    counter = int(time.time() // interval_seconds)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10 ** digits)
    return str(code).zfill(digits)


async def login_for_token(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    email: str,
    password: str,
) -> str:
    resp = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/auth/login",
        json_body={"email": email, "password": password},
    )
    if not resp["ok"] or resp["status_code"] != 200 or not isinstance(resp["payload"], dict):
        raise RuntimeError(f"login failed: {resp}")
    data = extract_enveloped_data(resp["payload"])
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError(f"login response missing access_token: {_json_preview(data)}")
    return str(token)


async def get_auth_context(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    access_token_env: str = "ACCESS_TOKEN",
    email_env: str = "AUTH_EMAIL",
    password_env: str = "AUTH_PASSWORD",
) -> dict[str, str]:
    token = env(access_token_env)
    if not token:
        email = env(email_env)
        password = env(password_env)
        if not email or not password:
            raise RuntimeError(
                f"Provide {access_token_env} or {email_env}/{password_env}"
            )
        token = await login_for_token(client, api_base=api_base, email=email, password=password)

    me = await request_json(
        client,
        "GET",
        f"{api_base}api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not me["ok"] or me["status_code"] != 200 or not isinstance(me["payload"], dict):
        raise RuntimeError(f"/auth/me failed: {me}")
    me_data = extract_enveloped_data(me["payload"])
    tenant = me_data.get("tenant") if isinstance(me_data, dict) else None
    tenant_id = tenant.get("tenant_id") if isinstance(tenant, dict) else None
    user_id = me_data.get("user_id") if isinstance(me_data, dict) else None
    role = me_data.get("role") if isinstance(me_data, dict) else None
    if not tenant_id:
        raise RuntimeError(f"Could not resolve tenant_id from /auth/me: {_json_preview(me_data)}")
    return {
        "access_token": str(token),
        "tenant_id": str(tenant_id),
        "user_id": str(user_id or ""),
        "role": str(role or ""),
    }


async def register_and_enable_mfa(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    name_prefix: str,
) -> dict[str, str]:
    unique = uuid.uuid4().hex[:10]
    email = f"{name_prefix}-{unique}@example.com"
    password = f"Pass@{uuid.uuid4().hex[:10]}"

    register_body = {
        "email": email,
        "password": password,
        "full_name": f"{name_prefix.title()} User {unique}",
        "tenant_name": f"{name_prefix.title()} Tenant {unique}",
        "tenant_type": "direct",
        "country": "IN",
        "terms_accepted": True,
    }
    register = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/auth/register",
        json_body=register_body,
    )
    if not register["ok"] or register["status_code"] != 201 or not isinstance(register["payload"], dict):
        raise RuntimeError(f"register failed: {register}")
    register_data = extract_enveloped_data(register["payload"])
    setup_token = register_data.get("setup_token") if isinstance(register_data, dict) else None
    tenant_id = register_data.get("tenant_id") if isinstance(register_data, dict) else None
    if not setup_token or not tenant_id:
        raise RuntimeError(f"register missing setup_token/tenant_id: {_json_preview(register_data)}")

    setup_resp = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json_body={},
    )
    if not setup_resp["ok"] or setup_resp["status_code"] != 200 or not isinstance(setup_resp["payload"], dict):
        raise RuntimeError(f"mfa/setup failed: {setup_resp}")
    setup_data = extract_enveloped_data(setup_resp["payload"])
    secret = setup_data.get("secret") if isinstance(setup_data, dict) else None
    if not secret:
        raise RuntimeError(f"mfa/setup missing secret: {_json_preview(setup_data)}")

    verify_resp = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/auth/mfa/verify-setup",
        headers={"Authorization": f"Bearer {setup_token}"},
        json_body={"code": generate_totp(str(secret))},
    )
    if not verify_resp["ok"] or verify_resp["status_code"] != 200 or not isinstance(verify_resp["payload"], dict):
        raise RuntimeError(f"mfa/verify-setup failed: {verify_resp}")
    verify_data = extract_enveloped_data(verify_resp["payload"])
    access_token = verify_data.get("access_token") if isinstance(verify_data, dict) else None
    refresh_token = verify_data.get("refresh_token") if isinstance(verify_data, dict) else None
    if not access_token:
        raise RuntimeError(f"mfa/verify-setup missing access_token: {_json_preview(verify_data)}")

    return {
        "email": email,
        "password": password,
        "tenant_id": str(tenant_id),
        "access_token": str(access_token),
        "refresh_token": str(refresh_token or ""),
    }


@dataclass(slots=True)
class StepResult:
    name: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationRun:
    name: str
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, status: str, **details: Any) -> None:
        self.steps.append(StepResult(name=name, status=status, details=details))

    @property
    def passed(self) -> bool:
        return all(step.status == "pass" for step in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "generated_at": utc_now_iso(),
            "passed": self.passed,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "details": step.details,
                }
                for step in self.steps
            ],
        }


def build_auth_headers(
    *,
    access_token: str | None = None,
    control_plane_token: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if control_plane_token:
        headers["X-Control-Plane-Token"] = control_plane_token
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def compute_razorpay_signature(secret: str, payload_bytes: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
