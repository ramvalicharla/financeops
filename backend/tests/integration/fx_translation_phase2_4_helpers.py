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

FX_TRANSLATION_TABLES: tuple[str, ...] = (
    "reporting_currency_definitions",
    "fx_translation_rule_definitions",
    "fx_rate_selection_policies",
    "fx_translation_runs",
    "fx_translated_metric_results",
    "fx_translated_variance_results",
    "fx_translation_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def fx_translation_phase2_4_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_fx_translation",
        error_context="fx translation phase2.4 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


