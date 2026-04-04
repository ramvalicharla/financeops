from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from _phase1_validation_lib import (
    ValidationRun,
    base_url,
    build_auth_headers,
    compute_razorpay_signature,
    env,
    extract_enveloped_data,
    get_auth_context,
    issue_control_plane_token,
    request_json,
    write_artifact,
)


async def _db_counts(database_url: str, invoice_id: str, provider_event_id: str) -> dict[str, Any]:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool
    except Exception as exc:
        return {"success": False, "error": f"sqlalchemy import failed: {exc}"}

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "ssl": True,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 15,
        },
    )
    try:
        async with engine.connect() as conn:
            payment_count = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM billing_payments WHERE invoice_id = :invoice_id"),
                    {"invoice_id": invoice_id},
                )
            ).scalar_one()
            event_count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM webhook_events
                        WHERE provider = 'razorpay' AND provider_event_id = :provider_event_id
                        """
                    ),
                    {"provider_event_id": provider_event_id},
                )
            ).scalar_one()
            return {
                "success": True,
                "payment_count": int(payment_count or 0),
                "webhook_event_count": int(event_count or 0),
            }
    except Exception as exc:
        return {"success": False, "error": str(exc) or exc.__class__.__name__}
    finally:
        await engine.dispose()


async def _post_raw_json(
    client: httpx.AsyncClient,
    *,
    url: str,
    payload: dict[str, Any],
    signature: str,
) -> dict[str, Any]:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    started = datetime.now(UTC)
    try:
        response = await client.post(
            url,
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": signature,
            },
            timeout=30,
        )
        try:
            body = response.json()
        except Exception:
            body = None
        return {
            "ok": True,
            "status_code": response.status_code,
            "payload": body,
            "text_preview": response.text[:1200],
            "sent_at": started.isoformat(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "payload": None,
            "text_preview": "",
            "error": str(exc) or exc.__class__.__name__,
            "sent_at": started.isoformat(),
        }


async def main() -> int:
    run = ValidationRun("webhook_lifecycle_validation")
    api_base = base_url()

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        auth = await get_auth_context(client, api_base=api_base)
        token = auth["access_token"]
        tenant_id = auth["tenant_id"]
        run.add("auth_context", "pass", tenant_id=tenant_id, role=auth.get("role"))

        control_plane_token = env("CONTROL_PLANE_TOKEN")
        if not control_plane_token:
            secret = env("SECRET_KEY")
            if secret:
                control_plane_token = issue_control_plane_token(
                    secret_key=secret,
                    tenant_id=tenant_id,
                    module_code="billing_validation",
                )

        if not control_plane_token:
            run.add(
                "control_plane_token",
                "fail",
                error="CONTROL_PLANE_TOKEN missing and SECRET_KEY not provided",
            )
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("control_plane_token", "pass")

        guarded_headers = build_auth_headers(
            access_token=token,
            control_plane_token=control_plane_token,
        )

        # Ensure subscription exists
        subscription_resp = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/billing/subscriptions/current",
            headers=guarded_headers,
        )
        if not subscription_resp["ok"] or subscription_resp["status_code"] != 200 or not isinstance(subscription_resp["payload"], dict):
            run.add("subscription_lookup", "fail", response=subscription_resp)
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1

        subscription_data = extract_enveloped_data(subscription_resp["payload"])
        subscription_item = subscription_data.get("item") if isinstance(subscription_data, dict) else None
        if not isinstance(subscription_item, dict) or not subscription_item.get("id"):
            run.add("subscription_lookup", "fail", error="No active subscription found for tenant")
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        subscription_id = str(subscription_item["id"])
        run.add("subscription_lookup", "pass", subscription_id=subscription_id)

        # Create invoice
        invoice_gen_resp = await request_json(
            client,
            "POST",
            f"{api_base}api/v1/billing/generate-invoice",
            headers={
                **guarded_headers,
                "Idempotency-Key": f"webhook-generate-{uuid.uuid4()}",
            },
            json_body={"subscription_id": subscription_id, "due_in_days": 7},
        )
        if not invoice_gen_resp["ok"] or invoice_gen_resp["status_code"] != 200 or not isinstance(invoice_gen_resp["payload"], dict):
            run.add("invoice_created", "fail", response=invoice_gen_resp)
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1

        invoice_data = extract_enveloped_data(invoice_gen_resp["payload"])
        invoice_id = str(invoice_data.get("invoice_id"))
        run.add("invoice_created", "pass", invoice_id=invoice_id, initial_status=invoice_data.get("status"))

        invoice_before_resp = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/billing/invoices/{invoice_id}",
            headers=guarded_headers,
        )
        if not invoice_before_resp["ok"] or invoice_before_resp["status_code"] != 200 or not isinstance(invoice_before_resp["payload"], dict):
            run.add("invoice_before_fetch", "fail", response=invoice_before_resp)
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1

        invoice_before_data = extract_enveloped_data(invoice_before_resp["payload"])
        provider_invoice_id = str(invoice_before_data.get("provider_invoice_id") or "")
        invoice_total = Decimal(str(invoice_before_data.get("total") or "0"))
        before_status = str(invoice_before_data.get("status") or "")
        run.add(
            "invoice_before_fetch",
            "pass",
            provider_invoice_id=provider_invoice_id,
            status=before_status,
        )

        if not provider_invoice_id:
            run.add("provider_invoice_id", "fail", error="provider_invoice_id is empty")
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("provider_invoice_id", "pass", provider_invoice_id=provider_invoice_id)

        razorpay_secret = env("RAZORPAY_KEY_SECRET")
        if not razorpay_secret:
            run.add("webhook_secret", "fail", error="RAZORPAY_KEY_SECRET is required for signed webhook simulation")
            artifact = write_artifact("webhook_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("webhook_secret", "pass")

        provider_event_id = f"evt_validation_{uuid.uuid4().hex}"
        payment_entity_id = f"pay_validation_{uuid.uuid4().hex}"
        payload = {
            "id": provider_event_id,
            "event": "invoice.paid",
            "payload": {
                "invoice": {
                    "entity": {
                        "id": provider_invoice_id,
                        "status": "paid",
                        "notes": {"tenant_id": tenant_id},
                    }
                },
                "payment": {
                    "entity": {
                        "id": payment_entity_id,
                        "invoice_id": provider_invoice_id,
                        "amount": int((invoice_total * Decimal("100")).quantize(Decimal("1"))),
                        "notes": {"tenant_id": tenant_id},
                    }
                },
            },
        }
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = compute_razorpay_signature(razorpay_secret, raw)

        db_url = env("MIGRATION_DATABASE_URL") or env("DATABASE_URL")
        counts_before = await _db_counts(db_url, invoice_id, provider_event_id) if db_url else {"success": False, "error": "database_url_missing"}

        webhook_url = f"{api_base}api/v1/billing/webhook?provider=razorpay&tenant_id={tenant_id}"

        first = await _post_raw_json(client, url=webhook_url, payload=payload, signature=signature)
        first_ok = bool(first.get("ok")) and first.get("status_code") == 200
        run.add("webhook_first_delivery", "pass" if first_ok else "fail", response=first)

        after_first_resp = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/billing/invoices/{invoice_id}",
            headers=guarded_headers,
        )
        after_first_status = None
        if after_first_resp["ok"] and after_first_resp["status_code"] == 200 and isinstance(after_first_resp["payload"], dict):
            after_first_data = extract_enveloped_data(after_first_resp["payload"])
            after_first_status = str(after_first_data.get("status") or "")
            run.add("invoice_after_first_webhook", "pass", status=after_first_status)
        else:
            run.add("invoice_after_first_webhook", "fail", response=after_first_resp)

        duplicate = await _post_raw_json(client, url=webhook_url, payload=payload, signature=signature)
        duplicate_ok = bool(duplicate.get("ok")) and duplicate.get("status_code") == 200
        run.add("webhook_duplicate_delivery", "pass" if duplicate_ok else "fail", response=duplicate)

        after_duplicate_resp = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/billing/invoices/{invoice_id}",
            headers=guarded_headers,
        )
        after_duplicate_status = None
        if after_duplicate_resp["ok"] and after_duplicate_resp["status_code"] == 200 and isinstance(after_duplicate_resp["payload"], dict):
            after_duplicate_data = extract_enveloped_data(after_duplicate_resp["payload"])
            after_duplicate_status = str(after_duplicate_data.get("status") or "")
            run.add("invoice_after_duplicate_webhook", "pass", status=after_duplicate_status)
        else:
            run.add("invoice_after_duplicate_webhook", "fail", response=after_duplicate_resp)

        counts_after_first = await _db_counts(db_url, invoice_id, provider_event_id) if db_url else {"success": False, "error": "database_url_missing"}
        counts_after_duplicate = await _db_counts(db_url, invoice_id, provider_event_id) if db_url else {"success": False, "error": "database_url_missing"}

        idempotent_status = (
            after_first_status == "paid"
            and after_duplicate_status == after_first_status
        )

        no_duplicate_entries = None
        if counts_before.get("success") and counts_after_first.get("success") and counts_after_duplicate.get("success"):
            delta_first = counts_after_first["payment_count"] - counts_before["payment_count"]
            delta_duplicate = counts_after_duplicate["payment_count"] - counts_after_first["payment_count"]
            no_duplicate_entries = delta_first == 1 and delta_duplicate == 0 and counts_after_duplicate["webhook_event_count"] == 1
        run.add(
            "webhook_idempotency_validation",
            "pass" if (idempotent_status and (no_duplicate_entries in {True, None})) else "fail",
            before_status=before_status,
            after_first_status=after_first_status,
            after_duplicate_status=after_duplicate_status,
            db_counts_before=counts_before,
            db_counts_after_first=counts_after_first,
            db_counts_after_duplicate=counts_after_duplicate,
            no_duplicate_entries=no_duplicate_entries,
        )

    payload = run.to_dict()
    artifact_path = write_artifact("webhook_validation.json", payload)
    print(json.dumps({"artifact": str(artifact_path), "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
