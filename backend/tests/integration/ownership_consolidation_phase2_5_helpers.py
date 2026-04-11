from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from tests.integration.temp_db_helpers import create_migrated_temp_database, drop_temp_database

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

OWNERSHIP_CONSOLIDATION_TABLES: tuple[str, ...] = (
    "ownership_structure_definitions",
    "ownership_relationships",
    "ownership_consolidation_rule_definitions",
    "minority_interest_rule_definitions",
    "ownership_consolidation_runs",
    "ownership_consolidation_metric_results",
    "ownership_consolidation_variance_results",
    "ownership_consolidation_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def ownership_phase2_5_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_ownership",
        error_context="ownership consolidation phase2.5 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)

