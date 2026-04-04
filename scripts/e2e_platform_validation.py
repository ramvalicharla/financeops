from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from _phase1_validation_lib import (
    ValidationRun,
    base_url,
    build_auth_headers,
    env,
    extract_enveloped_data,
    issue_control_plane_token,
    register_and_enable_mfa,
    request_json,
    write_artifact,
)


def _pick_first_template(templates_payload: Any) -> dict[str, Any] | None:
    if not isinstance(templates_payload, list) or not templates_payload:
        return None
    for item in templates_payload:
        if isinstance(item, dict) and item.get("code") == "SOFTWARE_SAAS":
            return item
    first = templates_payload[0]
    return first if isinstance(first, dict) else None


def _first_two_account_codes(accounts_payload: Any) -> list[str]:
    if not isinstance(accounts_payload, list):
        return []
    codes: list[str] = []
    for item in accounts_payload:
        if not isinstance(item, dict):
            continue
        code = item.get("account_code")
        if isinstance(code, str) and code and code not in codes:
            codes.append(code)
        if len(codes) >= 2:
            break
    return codes


async def _call(
    run: ValidationRun,
    client: httpx.AsyncClient,
    *,
    name: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    expected_statuses: set[int] | None = None,
) -> tuple[bool, dict[str, Any], Any]:
    expected = expected_statuses or {200}
    response = await request_json(
        client,
        method,
        url,
        headers=headers,
        params=params,
        json_body=body,
        timeout_seconds=45,
    )
    status_code = response.get("status_code")
    payload = response.get("payload")
    success = bool(response.get("ok")) and status_code in expected

    extracted: Any = None
    error: str | None = None
    if success and isinstance(payload, dict):
        try:
            extracted = extract_enveloped_data(payload)
        except Exception as exc:
            success = False
            error = str(exc)
    elif not success and response.get("error"):
        error = str(response.get("error"))

    run.add(
        name,
        "pass" if success else "fail",
        method=method,
        url=url,
        status_code=status_code,
        expected_statuses=sorted(expected),
        response_preview=response.get("text_preview"),
        error=error,
    )
    return success, response, extracted


async def main() -> int:
    run = ValidationRun("e2e_platform_validation")
    api_base = base_url()

    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        auth = await register_and_enable_mfa(client, api_base=api_base, name_prefix="phase1-e2e")
        access_token = auth["access_token"]
        tenant_id = auth["tenant_id"]
        run.add(
            "register_login_mfa",
            "pass",
            tenant_id=tenant_id,
            email=auth["email"],
        )

        control_plane_token = env("CONTROL_PLANE_TOKEN")
        if not control_plane_token:
            secret_key = env("SECRET_KEY")
            if secret_key:
                control_plane_token = issue_control_plane_token(
                    secret_key=secret_key,
                    tenant_id=tenant_id,
                    module_code="validation",
                )
        if not control_plane_token:
            run.add(
                "control_plane_token_resolution",
                "fail",
                error="CONTROL_PLANE_TOKEN missing and SECRET_KEY not provided for token generation",
            )
        else:
            run.add("control_plane_token_resolution", "pass")

        user_headers = build_auth_headers(access_token=access_token)
        guarded_headers = build_auth_headers(
            access_token=access_token,
            control_plane_token=control_plane_token,
            idempotency_key=f"e2e-{uuid.uuid4()}",
        )

        # Step 1: Org creation
        step1_ok, _, step1_data = await _call(
            run,
            client,
            name="step1_org_creation",
            method="POST",
            url=f"{api_base}api/v1/org-setup/step1",
            headers=user_headers,
            body={
                "group_name": f"Phase1 Group {uuid.uuid4().hex[:6]}",
                "country_of_incorp": "India",
                "country_code": "IN",
                "functional_currency": "INR",
                "reporting_currency": "INR",
            },
        )
        if not step1_ok or not isinstance(step1_data, dict):
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        group = step1_data.get("group") if isinstance(step1_data, dict) else None
        group_id = str(group.get("id")) if isinstance(group, dict) and group.get("id") else None
        if not group_id:
            run.add("resolve_group_id", "fail", error="group_id missing from step1 response")
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("resolve_group_id", "pass", group_id=group_id)

        # Step 2: Entity creation
        step2_ok, _, step2_data = await _call(
            run,
            client,
            name="step2_entity_creation",
            method="POST",
            url=f"{api_base}api/v1/org-setup/step2",
            headers=user_headers,
            body={
                "group_id": group_id,
                "entities": [
                    {
                        "legal_name": f"Phase1 Entity {uuid.uuid4().hex[:6]}",
                        "display_name": "Primary Entity",
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
        if not step2_ok or not isinstance(step2_data, dict):
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        entities = step2_data.get("entities")
        entity_id = None
        if isinstance(entities, list) and entities and isinstance(entities[0], dict):
            entity_id = str(entities[0].get("id"))
        if not entity_id:
            run.add("resolve_entity_id", "fail", error="entity_id missing from step2 response")
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("resolve_entity_id", "pass", entity_id=entity_id)

        # CoA template discovery + initialization
        templates_ok, _, templates_data = await _call(
            run,
            client,
            name="coa_templates_fetch",
            method="GET",
            url=f"{api_base}api/v1/coa/templates",
            headers=user_headers,
        )
        template = _pick_first_template(templates_data) if templates_ok else None
        template_id = str(template.get("id")) if isinstance(template, dict) else None
        if not template_id:
            run.add("resolve_template_id", "fail", error="No CoA template found")
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("resolve_template_id", "pass", template_id=template_id, template_code=template.get("code"))

        await _call(
            run,
            client,
            name="coa_initialization",
            method="POST",
            url=f"{api_base}api/v1/coa/tenant/initialise",
            headers=user_headers,
            body={"template_id": template_id},
        )

        # Step 4, 5, 6 to complete onboarding state for accounting guards
        await _call(
            run,
            client,
            name="step4_erp_config",
            method="POST",
            url=f"{api_base}api/v1/org-setup/step4",
            headers=user_headers,
            body={
                "configs": [
                    {
                        "org_entity_id": entity_id,
                        "erp_type": "MANUAL",
                        "is_primary": True,
                    }
                ]
            },
        )

        await _call(
            run,
            client,
            name="step5_template_mapping",
            method="POST",
            url=f"{api_base}api/v1/org-setup/step5",
            headers=user_headers,
            body={
                "entity_templates": [
                    {
                        "entity_id": entity_id,
                        "template_id": template_id,
                    }
                ]
            },
        )

        await _call(
            run,
            client,
            name="step6_finalize_onboarding",
            method="POST",
            url=f"{api_base}api/v1/org-setup/step6",
            headers=user_headers,
            body={"confirmed_mapping_ids": []},
        )

        # Fetch tenant accounts for journal lines
        accounts_ok, _, accounts_data = await _call(
            run,
            client,
            name="tenant_accounts_fetch",
            method="GET",
            url=f"{api_base}api/v1/coa/tenant/accounts",
            headers=user_headers,
        )
        account_codes = _first_two_account_codes(accounts_data if accounts_ok else [])
        if len(account_codes) < 2:
            run.add(
                "resolve_journal_accounts",
                "fail",
                error="Need at least two tenant CoA account codes to create journal",
            )
            artifact = write_artifact("e2e_validation.json", run.to_dict())
            print(json.dumps({"artifact": str(artifact), "passed": False}, indent=2))
            return 1
        run.add("resolve_journal_accounts", "pass", account_codes=account_codes)

        today = date.today().isoformat()

        # Journal create + lifecycle + posting
        journal_ok, _, journal_data = await _call(
            run,
            client,
            name="journal_create",
            method="POST",
            url=f"{api_base}api/v1/accounting/journals/",
            headers={**guarded_headers, "Idempotency-Key": f"jv-create-{uuid.uuid4()}"},
            body={
                "org_entity_id": entity_id,
                "journal_date": today,
                "reference": f"E2E-{uuid.uuid4().hex[:8]}",
                "narration": "Phase 1 e2e validation journal",
                "lines": [
                    {"account_code": account_codes[0], "debit": "100.00", "credit": "0", "memo": "line1"},
                    {"account_code": account_codes[1], "debit": "0", "credit": "100.00", "memo": "line2"},
                ],
            },
        )
        journal_id = None
        if journal_ok and isinstance(journal_data, dict):
            journal_id = journal_data.get("id")

        if journal_id:
            lifecycle_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Control-Plane-Token": str(control_plane_token),
            }
            await _call(
                run,
                client,
                name="journal_submit",
                method="POST",
                url=f"{api_base}api/v1/accounting/journals/{journal_id}/submit",
                headers=lifecycle_headers,
            )
            await _call(
                run,
                client,
                name="journal_review",
                method="POST",
                url=f"{api_base}api/v1/accounting/journals/{journal_id}/review",
                headers=lifecycle_headers,
            )
            await _call(
                run,
                client,
                name="journal_approve",
                method="POST",
                url=f"{api_base}api/v1/accounting/journals/{journal_id}/approve",
                headers=lifecycle_headers,
            )
            await _call(
                run,
                client,
                name="journal_post",
                method="POST",
                url=f"{api_base}api/v1/accounting/journals/{journal_id}/post",
                headers=lifecycle_headers,
            )

        date_30 = (datetime.now(UTC).date() - timedelta(days=30)).isoformat()

        await _call(
            run,
            client,
            name="trial_balance_generation",
            method="GET",
            url=f"{api_base}api/v1/accounting/trial-balance",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            params={"org_entity_id": entity_id, "as_of_date": today},
        )
        await _call(
            run,
            client,
            name="pnl_generation",
            method="GET",
            url=f"{api_base}api/v1/accounting/pnl",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            params={"org_entity_id": entity_id, "from_date": date_30, "to_date": today},
        )
        await _call(
            run,
            client,
            name="balance_sheet_generation",
            method="GET",
            url=f"{api_base}api/v1/accounting/balance-sheet",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            params={"org_entity_id": entity_id, "as_of_date": today},
        )
        await _call(
            run,
            client,
            name="cash_flow_generation",
            method="GET",
            url=f"{api_base}api/v1/accounting/cash-flow",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            params={"org_entity_id": entity_id, "from_date": date_30, "to_date": today},
        )

        # Optional modules
        await _call(
            run,
            client,
            name="optional_consolidation_summary",
            method="GET",
            url=f"{api_base}api/v1/consolidation/summary",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            expected_statuses={200, 422},
        )
        await _call(
            run,
            client,
            name="optional_fx_latest",
            method="GET",
            url=f"{api_base}api/v1/fx/rates/latest",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            expected_statuses={200, 404, 422},
        )
        await _call(
            run,
            client,
            name="optional_ai_anomalies",
            method="GET",
            url=f"{api_base}api/v1/ai/anomalies",
            headers=build_auth_headers(access_token=access_token, control_plane_token=control_plane_token),
            expected_statuses={200, 403, 422},
        )

    payload = run.to_dict()
    artifact_path = write_artifact("e2e_validation.json", payload)
    print(json.dumps({"artifact": str(artifact_path), "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
