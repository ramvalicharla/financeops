from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from financeops.db.session import AsyncSessionLocal
from financeops.seed import platform_owner as platform_owner_seed


async def seed_platform_owner() -> int:
    accounts = platform_owner_seed.collect_seed_accounts_from_env()
    if not accounts:
        print(
            "ERROR: No seed accounts configured. "
            "Set PLATFORM_OWNER_EMAIL/PLATFORM_OWNER_PASSWORD (optional PLATFORM_ADMIN_*)."
        )
        return 1

    original_session_factory = platform_owner_seed.AsyncSessionLocal
    platform_owner_seed.AsyncSessionLocal = AsyncSessionLocal
    try:
        result = await platform_owner_seed.seed_platform_users(accounts)
    finally:
        platform_owner_seed.AsyncSessionLocal = original_session_factory

    for account in accounts:
        print(f"Seeded account: {account.email} ({account.role.value})")
    print(
        f"Upsert completed. inserted={result['inserted']} existing={result['existing']} "
        f"total={result['upserted']}"
    )
    print("IMPORTANT: Password change and MFA setup are required on first login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed_platform_owner()))
