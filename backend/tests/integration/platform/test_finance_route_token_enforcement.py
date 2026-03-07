from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_missing_control_plane_token_blocks_revenue_run(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/revenue/run",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "reporting_currency": "USD",
            "rate_mode": "daily",
            "contracts": [
                {
                    "contract_number": "C-001",
                    "customer_id": "CUS-001",
                    "contract_currency": "USD",
                    "contract_start_date": "2026-01-01",
                    "contract_end_date": "2026-12-31",
                    "total_contract_value": "100.00",
                    "source_contract_reference": "SRC-001",
                    "policy_code": "REV-POL",
                    "policy_version": "v1",
                    "performance_obligations": [
                        {
                            "obligation_code": "OBL-1",
                            "description": "Single obligation",
                            "standalone_selling_price": "100.00",
                            "allocation_basis": "ssp",
                            "recognition_method": "straight_line",
                        }
                    ],
                    "contract_line_items": [
                        {
                            "line_code": "LINE-1",
                            "obligation_code": "OBL-1",
                            "line_amount": "100.00",
                            "line_currency": "USD",
                            "recognition_method": "straight_line",
                            "recognition_start_date": "2026-01-01",
                            "recognition_end_date": "2026-12-31",
                        }
                    ],
                }
            ],
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_invalid_control_plane_token_blocks_fx_fetch_live(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/fx/fetch-live",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "invalid.token",
        },
        json={
            "base_currency": "USD",
            "quote_currency": "EUR",
        },
    )
    assert response.status_code == 401
