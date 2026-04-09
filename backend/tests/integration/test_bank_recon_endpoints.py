from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.integration.entitlement_helpers import grant_boolean_entitlement


@pytest_asyncio.fixture(autouse=True)
async def _grant_bank_reconciliation_entitlement(async_session, test_user) -> None:
    await grant_boolean_entitlement(
        async_session,
        tenant_id=test_user.tenant_id,
        feature_name="bank_reconciliation",
        actor_user_id=test_user.id,
    )


@pytest.mark.asyncio
async def test_create_bank_statement(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.post(
        "/api/v1/bank-recon/statements",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "bank_name": "HDFC Bank",
            "account_number_masked": "XXXX1234",
            "currency": "INR",
            "period_year": 2025,
            "period_month": 3,
            "entity_name": "BankAPI_Entity",
            "opening_balance": "10000",
            "closing_balance": "12500",
            "file_name": "stmt.pdf",
            "file_hash": "a" * 64,
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert "statement_id" in data
    assert data["intent_id"]
    assert data["job_id"]
    assert data["bank_name"] == "HDFC Bank"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_add_bank_transaction(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}

    # First create a statement
    stmt_resp = await async_client.post(
        "/api/v1/bank-recon/statements",
        headers=headers,
        json={
            "bank_name": "SBI",
            "account_number_masked": "XXXX5678",
            "currency": "INR",
            "period_year": 2025,
            "period_month": 4,
            "entity_name": "TxnAPI_Entity",
            "opening_balance": "0",
            "closing_balance": "5000",
            "file_name": "april.pdf",
            "file_hash": "b" * 64,
        },
    )
    assert stmt_resp.status_code == 201
    stmt_id = stmt_resp.json()["data"]["statement_id"]

    txn_resp = await async_client.post(
        "/api/v1/bank-recon/transactions",
        headers=headers,
        json={
            "statement_id": stmt_id,
            "transaction_date": "2025-04-15",
            "description": "Customer receipt",
            "debit_amount": "0",
            "credit_amount": "5000",
            "balance": "5000",
        },
    )
    assert txn_resp.status_code == 201
    data = txn_resp.json()["data"]
    assert "transaction_id" in data
    assert data["intent_id"]
    assert data["job_id"]
    assert data["match_status"] == "unmatched"


@pytest.mark.asyncio
async def test_run_bank_reconciliation(
    async_client: AsyncClient, test_user, test_access_token: str
):
    headers = {"Authorization": f"Bearer {test_access_token}"}

    stmt_resp = await async_client.post(
        "/api/v1/bank-recon/statements",
        headers=headers,
        json={
            "bank_name": "Axis Bank",
            "account_number_masked": "XXXX9999",
            "currency": "INR",
            "period_year": 2025,
            "period_month": 5,
            "entity_name": "BankRun_Entity",
            "opening_balance": "0",
            "closing_balance": "1000",
            "file_name": "may.pdf",
            "file_hash": "c" * 64,
        },
    )
    stmt_id = stmt_resp.json()["data"]["statement_id"]

    await async_client.post(
        "/api/v1/bank-recon/transactions",
        headers=headers,
        json={
            "statement_id": stmt_id,
            "transaction_date": "2025-05-10",
            "description": "Receipt",
            "debit_amount": "0",
            "credit_amount": "1000",
            "balance": "1000",
        },
    )

    run_resp = await async_client.post(
        f"/api/v1/bank-recon/run/{stmt_id}",
        headers=headers,
    )
    assert run_resp.status_code == 201
    data = run_resp.json()["data"]
    assert "open_items_created" in data
    assert data["intent_id"]
    assert data["job_id"]
    assert data["open_items_created"] == 1


@pytest.mark.asyncio
async def test_list_bank_statements(
    async_client: AsyncClient, test_user, test_access_token: str
):
    response = await async_client.get(
        "/api/v1/bank-recon/statements",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "statements" in data


@pytest.mark.asyncio
async def test_bank_reconciliation_list_respects_limit(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {test_access_token}"}
    for idx in range(5):
        resp = await async_client.post(
            "/api/v1/bank-recon/statements",
            headers=headers,
            json={
                "bank_name": "HDFC Bank",
                "account_number_masked": f"XXXX{1200 + idx}",
                "currency": "INR",
                "period_year": 2025,
                "period_month": 6,
                "entity_name": f"BankLimit_{idx}",
                "opening_balance": "1000",
                "closing_balance": "1500",
                "file_name": f"limit_{idx}.pdf",
                "file_hash": ("f" * 60) + f"{idx:04d}",
            },
        )
        assert resp.status_code == 201

    response = await async_client.get(
        "/api/v1/bank-recon/statements?limit=2",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["items"]) == 2
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_bank_reconciliation_list_respects_skip(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {test_access_token}"}
    for idx in range(5):
        resp = await async_client.post(
            "/api/v1/bank-recon/statements",
            headers=headers,
            json={
                "bank_name": "SBI",
                "account_number_masked": f"XXXX{2200 + idx}",
                "currency": "INR",
                "period_year": 2025,
                "period_month": 7,
                "entity_name": f"BankSkip_{idx}",
                "opening_balance": "1000",
                "closing_balance": "1500",
                "file_name": f"skip_{idx}.pdf",
                "file_hash": ("e" * 60) + f"{idx:04d}",
            },
        )
        assert resp.status_code == 201

    response = await async_client.get(
        "/api/v1/bank-recon/statements?skip=3&limit=10",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["items"]) == 2


@pytest.mark.asyncio
async def test_bank_recon_requires_auth(async_client: AsyncClient):
    r = await async_client.get("/api/v1/bank-recon/statements")
    assert r.status_code == 401

