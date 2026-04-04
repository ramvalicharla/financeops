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


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def _collect_seed_accounts() -> list[dict[str, str | UserRole]]:
    """
    Platform seed instructions:
    1) Set PLATFORM_OWNER_EMAIL / PLATFORM_OWNER_PASSWORD / PLATFORM_OWNER_NAME
    2) Optional: set PLATFORM_ADMIN_EMAIL / PLATFORM_ADMIN_PASSWORD / PLATFORM_ADMIN_NAME
    3) Run: python scripts/seed_platform_owner.py

    Re-running is safe: users are upserted by email and updated in-place.
    To add another platform owner later, set PLATFORM_OWNER_* to that account and rerun.
    """
    accounts: list[dict[str, str | UserRole]] = []

    owner_email = _normalise_email(os.getenv("PLATFORM_OWNER_EMAIL") or "")
    owner_password = os.getenv("PLATFORM_OWNER_PASSWORD") or ""
    owner_name = (os.getenv("PLATFORM_OWNER_NAME") or "Platform Owner").strip()
    if owner_email and owner_password:
        accounts.append(
            {
                "email": owner_email,
                "password": owner_password,
                "full_name": owner_name or "Platform Owner",
                "role": UserRole.platform_owner,
            }
        )

    admin_email = _normalise_email(os.getenv("PLATFORM_ADMIN_EMAIL") or "")
    admin_password = os.getenv("PLATFORM_ADMIN_PASSWORD") or ""
    admin_name = (os.getenv("PLATFORM_ADMIN_NAME") or "Platform Admin").strip()
    if admin_email and admin_password:
        accounts.append(
            {
                "email": admin_email,
                "password": admin_password,
                "full_name": admin_name or "Platform Admin",
                "role": UserRole.platform_admin,
            }
        )

    return accounts


async def _ensure_platform_tenant() -> None:
    async with AsyncSessionLocal() as session:
        tenant = (
            await session.execute(
                select(IamTenant).where(IamTenant.id == PLATFORM_TENANT_ID)
            )
        ).scalar_one_or_none()
        if tenant is not None:
            return
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
        await session.commit()


async def seed_platform_owner() -> int:
    accounts = _collect_seed_accounts()
    if not accounts:
        print(
            "ERROR: No seed accounts configured. "
            "Set PLATFORM_OWNER_EMAIL/PLATFORM_OWNER_PASSWORD (optional PLATFORM_ADMIN_*)."
        )
        return 1

    await _ensure_platform_tenant()

    async with AsyncSessionLocal() as session:
        for account in accounts:
            user = (
                await session.execute(
                    select(IamUser).where(IamUser.email == str(account["email"]))
                )
            ).scalar_one_or_none()
            if user is None:
                user = IamUser(
                    tenant_id=PLATFORM_TENANT_ID,
                    email=str(account["email"]),
                    hashed_password=hash_password(str(account["password"])),
                    full_name=str(account["full_name"]),
                    role=account["role"],  # type: ignore[arg-type]
                    is_active=True,
                    is_verified=True,
                    mfa_enabled=False,
                    force_password_change=True,
                    force_mfa_setup=True,
                )
                session.add(user)
            else:
                user.tenant_id = PLATFORM_TENANT_ID
                user.email = str(account["email"])
                user.hashed_password = hash_password(str(account["password"]))
                user.full_name = str(account["full_name"])
                user.role = account["role"]  # type: ignore[assignment]
                user.is_active = True
                user.is_verified = True
                user.mfa_enabled = False
                user.force_password_change = True
                user.force_mfa_setup = True

        await session.commit()

    for account in accounts:
        role = account["role"]
        role_value = role.value if isinstance(role, UserRole) else str(role)
        print(f"Seeded account: {account['email']} ({role_value})")
    print("IMPORTANT: Password change and MFA setup are required on first login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(seed_platform_owner()))
