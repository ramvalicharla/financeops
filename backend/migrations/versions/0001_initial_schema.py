"""Initial schema — all Phase 0 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-03 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension with a clear infra-level failure message.
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except DBAPIError as exc:
        raise RuntimeError(
            "pgvector extension is required for FinanceOps migrations. "
            "Install/enable pgvector in the target PostgreSQL instance and retry. "
            "For local tests, use infra/docker-compose.test.yml (db_test uses pgvector/pgvector:pg16)."
        ) from exc

    # ── Enums (idempotent via exception handler — PostgreSQL has no CREATE TYPE IF NOT EXISTS) ──
    _enums = [
        ("tenant_type_enum", "('direct', 'ca_firm', 'enterprise_group')"),
        ("tenant_status_enum", "('active', 'suspended', 'pending')"),
        ("workspace_status_enum", "('active', 'suspended')"),
        ("user_role_enum", "('super_admin', 'finance_leader', 'finance_team', 'auditor', 'hr_manager', 'employee', 'read_only')"),
        ("credit_direction_enum", "('debit', 'credit')"),
        ("credit_tx_status_enum", "('pending', 'confirmed', 'released', 'failed')"),
        ("reservation_status_enum", "('pending', 'confirmed', 'released')"),
    ]
    for name, values in _enums:
        op.execute(
            f"DO $$ BEGIN CREATE TYPE {name} AS ENUM {values}; "
            f"EXCEPTION WHEN duplicate_object THEN NULL; END; $$"
        )

    # ── iam_tenants ────────────────────────────────────────────────────────
    op.create_table(
        "iam_tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("tenant_type", postgresql.ENUM("direct", "ca_firm", "enterprise_group", name="tenant_type_enum", create_type=False), nullable=False),
        sa.Column("parent_tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "suspended", "pending", name="tenant_status_enum", create_type=False), nullable=False),
        sa.ForeignKeyConstraint(["parent_tenant_id"], ["iam_tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_iam_tenants_tenant_id", "iam_tenants", ["tenant_id"])

    # ── iam_workspaces ─────────────────────────────────────────────────────
    op.create_table(
        "iam_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "suspended", name="workspace_status_enum", create_type=False), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_iam_workspaces_tenant_id", "iam_workspaces", ["tenant_id"])

    # ── iam_users ──────────────────────────────────────────────────────────
    op.create_table(
        "iam_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", postgresql.ENUM(
            "super_admin", "finance_leader", "finance_team", "auditor",
            "hr_manager", "employee", "read_only", name="user_role_enum", create_type=False
        ), nullable=False),
        sa.Column("totp_secret_encrypted", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_iam_users_tenant_id", "iam_users", ["tenant_id"])
    op.create_index("idx_iam_users_email", "iam_users", ["email"])

    # ── iam_sessions ───────────────────────────────────────────────────────
    op.create_table(
        "iam_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["iam_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_iam_sessions_user_id", "iam_sessions", ["user_id"])
    op.create_index("idx_iam_sessions_tenant_id", "iam_sessions", ["tenant_id"])
    op.create_index("idx_iam_sessions_token_hash", "iam_sessions", ["refresh_token_hash"])

    # ── audit_trail ────────────────────────────────────────────────────────
    op.create_table(
        "audit_trail",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(128), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("resource_name", sa.String(255), nullable=True),
        sa.Column("old_value_hash", sa.String(64), nullable=True),
        sa.Column("new_value_hash", sa.String(64), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="TIER 1: IMMUTABLE EVIDENTIARY — INSERT ONLY",
    )
    op.create_index("idx_audit_trail_tenant_created", "audit_trail", ["tenant_id", "created_at"])
    op.create_index("idx_audit_trail_resource", "audit_trail", ["tenant_id", "resource_type", "resource_id"])

    # ── credit_balances ────────────────────────────────────────────────────
    op.create_table(
        "credit_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("reserved", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    # ── credit_transactions ────────────────────────────────────────────────
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("direction", postgresql.ENUM("debit", "credit", name="credit_direction_enum", create_type=False), nullable=False),
        sa.Column("balance_before", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "pending", "confirmed", "released", "failed",
            name="credit_tx_status_enum", create_type=False
        ), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_credit_tx_tenant_created", "credit_transactions", ["tenant_id", "created_at"])

    # ── credit_reservations ────────────────────────────────────────────────
    op.create_table(
        "credit_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("task_type", sa.String(128), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "pending", "confirmed", "released", name="reservation_status_enum", create_type=False
        ), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_credit_reservations_tenant", "credit_reservations", ["tenant_id"])

    # ── ai_prompt_versions ─────────────────────────────────────────────────
    op.create_table(
        "ai_prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("model_target", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Integer, nullable=False),
        sa.Column("performance_notes", sa.Text, nullable=True),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_rate", sa.Float, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("prompt_key", "version", name="uq_prompt_key_version"),
    )
    op.create_index("idx_ai_prompt_versions_key", "ai_prompt_versions", ["prompt_key"])

    # ── Row Level Security ─────────────────────────────────────────────────
    financial_tables = ["audit_trail", "credit_transactions"]
    for table in financial_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
              ON {table}
              USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    # ── Seed AI Prompt Versions ────────────────────────────────────────────
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    router_prompt = """You are a routing agent.

You do NOT answer the user's request.
You do NOT generate solutions.
You ONLY decide which local LLM should handle the task.

Available models:
1) deepseek-coder (local) → coding, refactoring, platform logic, structured technical output
2) mistral (local) → finance writing, summaries, explanations, policy drafts, general reasoning
3) cloud-70b (cloud) → high accuracy required, multi-step reasoning, governance/compliance critical

Your job:
- Read the user's input
- Classify the task
- Select ONE model
- Output JSON only

Classification rules:
- If the task involves code, debugging, refactoring, architecture, scripts, APIs, tests → use deepseek-coder
- If the task involves finance, accounting, explanation, summaries, memos, policies, checklists → use mistral
- If unsure, choose deepseek-coder
- If the task is high-risk (legal/compliance), multi-step reasoning, or must be highly accurate → choose cloud-70b

Output format (JSON only, no extra text):

{
  "task_type": "<short classification>",
  "selected_model": "<deepseek-coder | mistral | cloud-70b>",
  "reason": "<one sentence reason>"
}"""

    deepseek_prompt = """You are DeepSeek Coder operating as a senior software engineer.

You produce:
- precise, correct code
- clean structure
- minimal verbosity
- no hallucinated APIs
- no fake files or steps

Rules:
- Assume code will be executed or reviewed by a real engineer
- Prefer correctness over cleverness
- If information is missing, ask a clear clarification question
- When generating code, explain briefly and then show the code
- When asked for prompts, produce Codex-ready prompts

Focus areas:
- backend systems
- APIs
- scripts
- platform logic
- refactoring
- debugging"""

    mistral_prompt = """You are Mistral operating as a senior finance and business professional.

You produce:
- clear explanations
- structured finance outputs
- professional memos
- policies
- checklists
- summaries

Rules:
- Assume the reader is a senior executive or auditor
- Be accurate and conservative
- Use simple, professional language
- Avoid unnecessary jargon
- Structure outputs with headings or bullets where helpful

Focus areas:
- finance
- accounting
- policies
- business explanations
- summaries
- documentation"""

    op.bulk_insert(
        sa.table(
            "ai_prompt_versions",
            sa.column("id", postgresql.UUID()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("prompt_key", sa.String()),
            sa.column("version", sa.Integer()),
            sa.column("prompt_text", sa.Text()),
            sa.column("model_target", sa.String()),
            sa.column("is_active", sa.Integer()),
        ),
        [
            {
                "id": str(uuid.uuid4()),
                "created_at": now,
                "prompt_key": "router_system",
                "version": 1,
                "prompt_text": router_prompt,
                "model_target": "router",
                "is_active": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "created_at": now,
                "prompt_key": "deepseek_system",
                "version": 1,
                "prompt_text": deepseek_prompt,
                "model_target": "deepseek-coder",
                "is_active": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "created_at": now,
                "prompt_key": "mistral_system",
                "version": 1,
                "prompt_text": mistral_prompt,
                "model_target": "mistral",
                "is_active": 1,
            },
        ],
    )


def downgrade() -> None:
    # Drop RLS policies
    financial_tables = ["audit_trail", "credit_transactions"]
    for table in financial_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("ai_prompt_versions")
    op.drop_table("credit_reservations")
    op.drop_table("credit_transactions")
    op.drop_table("credit_balances")
    op.drop_table("audit_trail")
    op.drop_table("iam_sessions")
    op.drop_table("iam_users")
    op.drop_table("iam_workspaces")
    op.drop_table("iam_tenants")

    # Drop enums
    for enum_name in [
        "reservation_status_enum", "credit_tx_status_enum", "credit_direction_enum",
        "user_role_enum", "workspace_status_enum", "tenant_status_enum", "tenant_type_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.execute("DROP EXTENSION IF EXISTS vector")
