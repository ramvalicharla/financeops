from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.session import AsyncSessionLocal
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

PLATFORM_TENANT_ID = uuid.UUID(int=0)


@dataclass(frozen=True)
class SeedAccount:
    email: str
    password: str
    full_name: str
    role: UserRole


def _normalise_email(value: str) -> str:
    return value.strip().lower()


def collect_seed_accounts_from_env() -> list[SeedAccount]:
    accounts: list[SeedAccount] = []

    owner_email = _normalise_email(os.getenv("PLATFORM_OWNER_EMAIL") or "")
    owner_password = os.getenv("PLATFORM_OWNER_PASSWORD") or ""
    owner_name = (os.getenv("PLATFORM_OWNER_NAME") or "Platform Owner").strip()
    if owner_email and owner_password:
        accounts.append(
            SeedAccount(
                email=owner_email,
                password=owner_password,
                full_name=owner_name or "Platform Owner",
                role=UserRole.platform_owner,
            )
        )

    admin_email = _normalise_email(os.getenv("PLATFORM_ADMIN_EMAIL") or "")
    admin_password = os.getenv("PLATFORM_ADMIN_PASSWORD") or ""
    admin_name = (os.getenv("PLATFORM_ADMIN_NAME") or "Platform Admin").strip()
    if admin_email and admin_password:
        accounts.append(
            SeedAccount(
                email=admin_email,
                password=admin_password,
                full_name=admin_name or "Platform Admin",
                role=UserRole.platform_admin,
            )
        )

    return accounts


async def _ensure_platform_tenant(session: AsyncSession) -> None:
    record_data = {
        "display_name": "FinanceOps Platform",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    tenant_stmt = pg_insert(IamTenant.__table__).values(
        {
            "id": PLATFORM_TENANT_ID,
            "tenant_id": PLATFORM_TENANT_ID,
            "chain_hash": compute_chain_hash(record_data, GENESIS_HASH),
            "previous_hash": GENESIS_HASH,
            "created_at": datetime.now(timezone.utc),
            "display_name": "FinanceOps Platform",
            "slug": "platform-00000000",
            "tenant_type": TenantType.direct.value,
            "parent_tenant_id": None,
            "country": "US",
            "timezone": "UTC",
            "status": TenantStatus.active.value,
            "is_platform_tenant": True,
        }
    ).on_conflict_do_nothing(index_elements=["id"])
    await session.execute(tenant_stmt)
    await session.flush()


async def seed_platform_users(
    accounts: list[SeedAccount],
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, Any]:
    if not accounts:
        return {
            "status": "skipped",
            "reason": "no_seed_accounts_configured",
            "inserted": 0,
            "existing": 0,
            "upserted": 0,
        }

    async with session_factory() as session:
        await _ensure_platform_tenant(session)

        account_emails = [item.email for item in accounts]
        existing_rows = (
            await session.execute(
                select(IamUser.email).where(IamUser.email.in_(account_emails))
            )
        ).scalars().all()
        existing_emails = {str(email).lower() for email in existing_rows}

        now = datetime.now(timezone.utc)
        rows: list[dict[str, Any]] = []
        for account in accounts:
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "tenant_id": PLATFORM_TENANT_ID,
                    "email": account.email,
                    "hashed_password": hash_password(account.password),
                    "full_name": account.full_name,
                    "role": account.role,
                    "is_active": True,
                    "is_verified": True,
                    "mfa_enabled": False,
                    "force_password_change": True,
                    "force_mfa_setup": True,
                    "created_at": now,
                }
            )

        upsert_stmt = pg_insert(IamUser.__table__).values(rows)
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["email"],
            set_={
                "tenant_id": upsert_stmt.excluded.tenant_id,
                "hashed_password": upsert_stmt.excluded.hashed_password,
                "full_name": upsert_stmt.excluded.full_name,
                "role": upsert_stmt.excluded.role,
                "is_active": upsert_stmt.excluded.is_active,
                "is_verified": upsert_stmt.excluded.is_verified,
                "mfa_enabled": upsert_stmt.excluded.mfa_enabled,
                "force_password_change": upsert_stmt.excluded.force_password_change,
                "force_mfa_setup": upsert_stmt.excluded.force_mfa_setup,
            },
        )
        await session.execute(upsert_stmt)
        await session.commit()

    existing_count = len([email for email in account_emails if email in existing_emails])
    inserted_count = len(account_emails) - existing_count
    return {
        "status": "seeded",
        "reason": "upsert_completed",
        "inserted": inserted_count,
        "existing": existing_count,
        "upserted": len(account_emails),
    }


async def seed_platform_users_from_env(
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> dict[str, Any]:
    return await seed_platform_users(
        collect_seed_accounts_from_env(),
        session_factory=session_factory,
    )
