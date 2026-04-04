from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx

from _phase1_validation_lib import (
    ValidationRun,
    base_url,
    build_auth_headers,
    extract_enveloped_data,
    register_and_enable_mfa,
    request_json,
    write_artifact,
)


async def _step1_and_step2(
    client: httpx.AsyncClient,
    *,
    api_base: str,
    access_token: str,
    tenant_label: str,
) -> dict[str, Any]:
    headers = build_auth_headers(access_token=access_token)

    step1 = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/org-setup/step1",
        headers=headers,
        json_body={
            "group_name": f"{tenant_label}-group-{uuid.uuid4().hex[:6]}",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    if not step1["ok"] or step1["status_code"] != 200 or not isinstance(step1["payload"], dict):
        return {"success": False, "error": f"step1_failed:{step1}"}
    step1_data = extract_enveloped_data(step1["payload"])
    group_id = step1_data.get("group", {}).get("id") if isinstance(step1_data, dict) else None
    if not group_id:
        return {"success": False, "error": "group_id_missing"}

    step2 = await request_json(
        client,
        "POST",
        f"{api_base}api/v1/org-setup/step2",
        headers=headers,
        json_body={
            "group_id": group_id,
            "entities": [
                {
                    "legal_name": f"{tenant_label}-entity-{uuid.uuid4().hex[:6]}",
                    "display_name": f"{tenant_label}-entity-1",
                    "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                    "country_code": "IN",
                    "functional_currency": "INR",
                    "reporting_currency": "INR",
                    "fiscal_year_start": 4,
                    "applicable_gaap": "INDAS",
                }
            ],
        },
    )
    if not step2["ok"] or step2["status_code"] != 200 or not isinstance(step2["payload"], dict):
        return {"success": False, "error": f"step2_failed:{step2}"}
    step2_data = extract_enveloped_data(step2["payload"])
    entities = step2_data.get("entities") if isinstance(step2_data, dict) else None
    entity_id = entities[0].get("id") if isinstance(entities, list) and entities and isinstance(entities[0], dict) else None
    if not entity_id:
        return {"success": False, "error": "entity_id_missing"}

    return {
        "success": True,
        "group_id": str(group_id),
        "entity_id": str(entity_id),
        "step1": step1,
        "step2": step2,
    }


async def main() -> int:
    run = ValidationRun("tenant_isolation_concurrency_validation")
    api_base = base_url()

    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
        # Create two isolated tenants
        tenant_a, tenant_b = await asyncio.gather(
            register_and_enable_mfa(client, api_base=api_base, name_prefix="tenant-a"),
            register_and_enable_mfa(client, api_base=api_base, name_prefix="tenant-b"),
        )
        run.add(
            "create_two_tenants",
            "pass",
            tenant_a_id=tenant_a["tenant_id"],
            tenant_b_id=tenant_b["tenant_id"],
        )

        # Seed baseline org/entity in both tenants concurrently
        setup_a, setup_b = await asyncio.gather(
            _step1_and_step2(
                client,
                api_base=api_base,
                access_token=tenant_a["access_token"],
                tenant_label="tenant-a",
            ),
            _step1_and_step2(
                client,
                api_base=api_base,
                access_token=tenant_b["access_token"],
                tenant_label="tenant-b",
            ),
        )
        setup_ok = setup_a.get("success") and setup_b.get("success")
        run.add("parallel_setup", "pass" if setup_ok else "fail", tenant_a_setup=setup_a, tenant_b_setup=setup_b)
        if not setup_ok:
            artifact = write_artifact("tenant_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1

        tenant_a_headers = build_auth_headers(access_token=tenant_a["access_token"])
        tenant_b_headers = build_auth_headers(access_token=tenant_b["access_token"])

        # Cross-tenant direct entity access should fail
        cross_a_to_b = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/org-setup/entities/{setup_b['entity_id']}",
            headers=tenant_a_headers,
        )
        cross_b_to_a = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/org-setup/entities/{setup_a['entity_id']}",
            headers=tenant_b_headers,
        )
        cross_ok = cross_a_to_b.get("status_code") == 404 and cross_b_to_a.get("status_code") == 404
        run.add(
            "cross_tenant_entity_access_blocked",
            "pass" if cross_ok else "fail",
            tenant_a_to_b=cross_a_to_b,
            tenant_b_to_a=cross_b_to_a,
        )

        # Concurrent read/write burst
        async def _tenant_burst(token: str, group_id: str, label: str) -> list[dict[str, Any]]:
            headers = build_auth_headers(access_token=token)
            tasks = []
            for idx in range(5):
                tasks.append(
                    request_json(
                        client,
                        "POST",
                        f"{api_base}api/v1/org-setup/step2",
                        headers=headers,
                        json_body={
                            "group_id": group_id,
                            "entities": [
                                {
                                    "legal_name": f"{label}-burst-{idx}-{uuid.uuid4().hex[:4]}",
                                    "display_name": f"{label}-burst-{idx}",
                                    "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                                    "country_code": "IN",
                                    "functional_currency": "INR",
                                    "reporting_currency": "INR",
                                    "fiscal_year_start": 4,
                                    "applicable_gaap": "INDAS",
                                }
                            ],
                        },
                    )
                )
                tasks.append(
                    request_json(
                        client,
                        "GET",
                        f"{api_base}api/v1/org-setup/summary",
                        headers=headers,
                    )
                )
            return await asyncio.gather(*tasks)

        burst_a, burst_b = await asyncio.gather(
            _tenant_burst(tenant_a["access_token"], setup_a["group_id"], "tenant-a"),
            _tenant_burst(tenant_b["access_token"], setup_b["group_id"], "tenant-b"),
        )
        burst_ok = all(item.get("ok") and item.get("status_code") == 200 for item in (burst_a + burst_b))
        run.add("concurrent_read_write_burst", "pass" if burst_ok else "fail")

        # Verify summaries do not leak other tenant entity ids
        summary_a = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/org-setup/summary",
            headers=tenant_a_headers,
        )
        summary_b = await request_json(
            client,
            "GET",
            f"{api_base}api/v1/org-setup/summary",
            headers=tenant_b_headers,
        )

        leak_detected = False
        leaked_refs: list[str] = []
        if summary_a.get("ok") and summary_a.get("status_code") == 200 and isinstance(summary_a.get("payload"), dict):
            data_a = extract_enveloped_data(summary_a["payload"])
            text_a = json.dumps(data_a, default=str)
            if setup_b["entity_id"] in text_a or tenant_b["tenant_id"] in text_a:
                leak_detected = True
                leaked_refs.append("tenant_a_contains_tenant_b")

        if summary_b.get("ok") and summary_b.get("status_code") == 200 and isinstance(summary_b.get("payload"), dict):
            data_b = extract_enveloped_data(summary_b["payload"])
            text_b = json.dumps(data_b, default=str)
            if setup_a["entity_id"] in text_b or tenant_a["tenant_id"] in text_b:
                leak_detected = True
                leaked_refs.append("tenant_b_contains_tenant_a")

        run.add(
            "summary_no_cross_tenant_leakage",
            "pass" if not leak_detected else "fail",
            leak_detected=leak_detected,
            leaked_refs=leaked_refs,
            summary_a_status=summary_a.get("status_code"),
            summary_b_status=summary_b.get("status_code"),
        )

    payload = run.to_dict()
    artifact_path = write_artifact("tenant_validation.json", payload)
    print(json.dumps({"artifact": str(artifact_path), "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
