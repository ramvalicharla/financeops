from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)


async def seed_platform_owner() -> int:
    email = (os.getenv("PLATFORM_OWNER_EMAIL") or "").strip().lower()
    password = os.getenv("PLATFORM_OWNER_PASSWORD") or ""
    full_name = (os.getenv("PLATFORM_OWNER_NAME") or "Platform Owner").strip()

    if not email or not password:
        print("ERROR: PLATFORM_OWNER_EMAIL and PLATFORM_OWNER_PASSWORD are required")
        return 1

    async with AsyncSessionLocal() as session:
        existing_owner = (
            await session.execute(
                select(IamUser).where(IamUser.role == UserRole.platform_owner)
            )
        ).scalar_one_or_none()
        if existing_owner is not None:
            print("Platform owner already exists — skipping")
            return 0

        tenant = (
            await session.execute(
                select(IamTenant).where(IamTenant.id == PLATFORM_TENANT_ID)
            )
        ).scalar_one_or_none()
        if tenant is None:
            record_data = {
                "display_name": "FinanceOps Platform",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            }
            chain_hash = compute_chain_hash(record_data, GENESIS_HASH)
            tenant = IamTenant(
                id=PLATFORM_TENANT_ID,
                tenant_id=PLATFORM_TENANT_ID,
                display_name="FinanceOps Platform",
                tenant_type=TenantType.direct,
                country="US",
                timezone="UTC",
                status=TenantStatus.active,
                is_platform_tenant=True,
                chain_hash=chain_hash,
                previous_hash=GENESIS_HASH,
            )
            session.add(tenant)
            await session.flush()

        owner = IamUser(
            tenant_id=PLATFORM_TENANT_ID,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name or "Platform Owner",
            role=UserRole.platform_owner,
            is_active=True,
            mfa_enabled=False,
            force_mfa_setup=True,
        )
        session.add(owner)
        await session.commit()

    print(f"Platform owner created: {email}")
    print("IMPORTANT: MFA setup will be required on first login.")
    print(f"Add to .env: PLATFORM_OWNER_EMAIL={email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed_platform_owner()))

