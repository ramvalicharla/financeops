from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.board_pack_phase1f7_helpers import ensure_tenant_context


async def _insert_definition(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    code: str,
    supersedes_id: uuid.UUID | None,
    status: str,
    effective_from: date,
    row_id: uuid.UUID | None = None,
) -> uuid.UUID:
    row_id = row_id or uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO board_pack_definitions
              (id, tenant_id, chain_hash, previous_hash, organisation_id,
               board_pack_code, board_pack_name, audience_scope,
               section_order_json, inclusion_config_json, version_token,
               effective_from, effective_to, supersedes_id, status, created_by)
            VALUES
              (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
               :board_pack_code, :board_pack_name, 'board',
               '{}'::jsonb, '{}'::jsonb, :version_token,
               :effective_from, NULL, :supersedes_id, :status, :created_by)
            """
        ),
        {
            "id": str(row_id),
            "tenant_id": str(tenant_id),
            "chain_hash": "1" * 64,
            "previous_hash": "0" * 64,
            "organisation_id": str(organisation_id),
            "board_pack_code": code,
            "board_pack_name": code,
            "version_token": uuid.uuid4().hex,
            "effective_from": effective_from,
            "supersedes_id": str(supersedes_id) if supersedes_id else None,
            "status": status,
            "created_by": str(tenant_id),
        },
    )
    return row_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_definition_allows_valid_linear_supersession(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            await ensure_tenant_context(session, tenant_id)
            code = f"BOARD_PACK_{uuid.uuid4().hex[:6]}"
            v1 = await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=code,
                supersedes_id=None,
                status="active",
                effective_from=date(2026, 1, 1),
            )
            v2 = await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=code,
                supersedes_id=v1,
                status="candidate",
                effective_from=date(2026, 2, 1),
            )
            assert v2 is not None
        finally:
            if session.in_transaction():
                await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_definition_rejects_self_cross_branch_and_second_active(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            await ensure_tenant_context(session, tenant_id)

            row_id = uuid.uuid4()
            with pytest.raises(DBAPIError, match="self-supersession"):
                await _insert_definition(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=tenant_id,
                    code="BOARD_SELF",
                    supersedes_id=row_id,
                    status="candidate",
                    effective_from=date(2026, 1, 1),
                    row_id=row_id,
                )
                await session.flush()
            if session.in_transaction():
                await session.rollback()
            await ensure_tenant_context(session, tenant_id)

            parent = await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=f"BOARD_A_{uuid.uuid4().hex[:4]}",
                supersedes_id=None,
                status="active",
                effective_from=date(2026, 1, 1),
            )
            with pytest.raises(DBAPIError, match="across different codes"):
                await _insert_definition(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=tenant_id,
                    code=f"BOARD_B_{uuid.uuid4().hex[:4]}",
                    supersedes_id=parent,
                    status="candidate",
                    effective_from=date(2026, 2, 1),
                )
                await session.flush()
            if session.in_transaction():
                await session.rollback()
            await ensure_tenant_context(session, tenant_id)

            branch_code = f"BOARD_BRANCH_{uuid.uuid4().hex[:4]}"
            root = await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=branch_code,
                supersedes_id=None,
                status="candidate",
                effective_from=date(2026, 1, 1),
            )
            await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=branch_code,
                supersedes_id=root,
                status="candidate",
                effective_from=date(2026, 2, 1),
            )
            with pytest.raises(DBAPIError, match="branching"):
                await _insert_definition(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=tenant_id,
                    code=branch_code,
                    supersedes_id=root,
                    status="candidate",
                    effective_from=date(2026, 3, 1),
                )
                await session.flush()
            if session.in_transaction():
                await session.rollback()
            await ensure_tenant_context(session, tenant_id)

            active_code = f"BOARD_ACTIVE_{uuid.uuid4().hex[:4]}"
            await _insert_definition(
                session,
                tenant_id=tenant_id,
                organisation_id=tenant_id,
                code=active_code,
                supersedes_id=None,
                status="active",
                effective_from=date(2026, 1, 1),
            )
            with pytest.raises(IntegrityError, match="uq_board_pack_definitions_one_active"):
                await _insert_definition(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=tenant_id,
                    code=active_code,
                    supersedes_id=None,
                    status="active",
                    effective_from=date(2026, 2, 1),
                )
                await session.flush()
        finally:
            if session.in_transaction():
                await session.rollback()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_section_template_and_rule_reject_self_supersession(
    board_pack_phase1f7_engine,
) -> None:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            tenant_id = uuid.uuid4()
            await ensure_tenant_context(session, tenant_id)

            with pytest.raises(DBAPIError, match="self-supersession"):
                row_id = uuid.uuid4()
                await session.execute(
                    text(
                        """
                        INSERT INTO board_pack_section_definitions
                          (id, tenant_id, chain_hash, previous_hash, organisation_id,
                           section_code, section_name, section_type, render_logic_json,
                           section_order_default, narrative_template_ref,
                           risk_inclusion_rule_json, anomaly_inclusion_rule_json,
                           metric_inclusion_rule_json, version_token, effective_from,
                           supersedes_id, status, created_by)
                        VALUES
                          (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                           'SEC_SELF', 'SEC_SELF', 'executive_summary', '{}'::jsonb,
                           1, NULL, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                           :version_token, :effective_from, :supersedes_id, 'candidate', :created_by)
                        """
                    ),
                    {
                        "id": str(row_id),
                        "tenant_id": str(tenant_id),
                        "chain_hash": "1" * 64,
                        "previous_hash": "0" * 64,
                        "organisation_id": str(tenant_id),
                        "version_token": uuid.uuid4().hex,
                        "effective_from": date(2026, 1, 1),
                        "supersedes_id": str(row_id),
                        "created_by": str(tenant_id),
                    },
                )
                await session.flush()

            if session.in_transaction():
                await session.rollback()
            await ensure_tenant_context(session, tenant_id)

            with pytest.raises(DBAPIError, match="self-supersession"):
                row_id = uuid.uuid4()
                await session.execute(
                    text(
                        """
                        INSERT INTO narrative_templates
                          (id, tenant_id, chain_hash, previous_hash, organisation_id,
                           template_code, template_name, template_type, template_text,
                           template_body_json, placeholder_schema_json, version_token,
                           effective_from, supersedes_id, status, created_by)
                        VALUES
                          (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                           'TMP_SELF', 'TMP_SELF', 'executive_summary_template', 'x',
                           '{}'::jsonb, '{}'::jsonb, :version_token,
                           :effective_from, :supersedes_id, 'candidate', :created_by)
                        """
                    ),
                    {
                        "id": str(row_id),
                        "tenant_id": str(tenant_id),
                        "chain_hash": "1" * 64,
                        "previous_hash": "0" * 64,
                        "organisation_id": str(tenant_id),
                        "version_token": uuid.uuid4().hex,
                        "effective_from": date(2026, 1, 1),
                        "supersedes_id": str(row_id),
                        "created_by": str(tenant_id),
                    },
                )
                await session.flush()

            if session.in_transaction():
                await session.rollback()
            await ensure_tenant_context(session, tenant_id)

            with pytest.raises(DBAPIError, match="self-supersession"):
                row_id = uuid.uuid4()
                await session.execute(
                    text(
                        """
                        INSERT INTO board_pack_inclusion_rules
                          (id, tenant_id, chain_hash, previous_hash, organisation_id,
                           rule_code, rule_name, rule_type, inclusion_logic_json,
                           version_token, effective_from, supersedes_id, status, created_by)
                        VALUES
                          (:id, :tenant_id, :chain_hash, :previous_hash, :organisation_id,
                           'RULE_SELF', 'RULE_SELF', 'top_severity_issues', '{}'::jsonb,
                           :version_token, :effective_from, :supersedes_id, 'candidate', :created_by)
                        """
                    ),
                    {
                        "id": str(row_id),
                        "tenant_id": str(tenant_id),
                        "chain_hash": "1" * 64,
                        "previous_hash": "0" * 64,
                        "organisation_id": str(tenant_id),
                        "version_token": uuid.uuid4().hex,
                        "effective_from": date(2026, 1, 1),
                        "supersedes_id": str(row_id),
                        "created_by": str(tenant_id),
                    },
                )
                await session.flush()
        finally:
            if session.in_transaction():
                await session.rollback()
