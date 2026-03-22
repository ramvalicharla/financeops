"""Encrypt existing webhook and ERP secrets at rest.

Revision ID: 0036_encrypt_existing_secrets
Revises: 0035_fix_float_columns
Create Date: 2026-03-22 00:00:00.000000

Security remediation: encrypting plaintext webhook and ERP secrets.
This is an explicit exception to the append-only policy for
non-financial operational config columns only. Approved by audit
finding Codex-F003. Financial tables are not affected.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from financeops.core.security import decrypt_field, encrypt_field
from financeops.db.append_only import create_trigger_sql, drop_trigger_sql

revision: str = "0036_encrypt_existing_secrets"
down_revision: str | None = "0035_fix_float_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _is_encrypted(candidate: str | None) -> bool:
    text_value = str(candidate or "").strip()
    if not text_value:
        return False
    try:
        _ = decrypt_field(text_value)
        return True
    except Exception:
        return False


def _upgrade_delivery_webhook_secrets() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, config
            FROM delivery_schedules
            WHERE config ? 'webhook_secret'
               OR config ? 'webhook_secret_enc'
            """
        )
    ).mappings()
    for row in rows:
        config = dict(row["config"] or {})
        encrypted = str(config.get("webhook_secret_enc") or "").strip()
        if encrypted and _is_encrypted(encrypted):
            config.pop("webhook_secret", None)
            bind.execute(
                sa.text(
                    """
                    UPDATE delivery_schedules
                    SET config = CAST(:config_json AS jsonb), updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": row["id"], "config_json": json.dumps(config)},
            )
            continue

        plaintext = str(config.get("webhook_secret") or "").strip()
        if not plaintext:
            continue

        config["webhook_secret_enc"] = encrypt_field(plaintext)
        config.pop("webhook_secret", None)
        bind.execute(
            sa.text(
                """
                UPDATE delivery_schedules
                SET config = CAST(:config_json AS jsonb), updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": row["id"], "config_json": json.dumps(config)},
        )


def _upgrade_external_connection_secrets() -> None:
    bind = op.get_bind()

    # Controlled security remediation: temporarily disable append-only trigger.
    op.execute(drop_trigger_sql("external_connections"))
    try:
        rows = bind.execute(
            sa.text(
                """
                SELECT id, secret_ref
                FROM external_connections
                WHERE secret_ref IS NOT NULL
                  AND secret_ref <> ''
                """
            )
        ).mappings()
        for row in rows:
            secret_ref = str(row["secret_ref"] or "").strip()
            if not secret_ref or _is_encrypted(secret_ref):
                continue
            bind.execute(
                sa.text(
                    """
                    UPDATE external_connections
                    SET secret_ref = :secret_ref
                    WHERE id = :id
                    """
                ),
                {"id": row["id"], "secret_ref": encrypt_field(secret_ref)},
            )
    finally:
        op.execute(create_trigger_sql("external_connections"))


def _downgrade_delivery_webhook_secrets() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, config
            FROM delivery_schedules
            WHERE config ? 'webhook_secret_enc'
            """
        )
    ).mappings()
    for row in rows:
        config = dict(row["config"] or {})
        encrypted = str(config.get("webhook_secret_enc") or "").strip()
        if not encrypted:
            continue
        try:
            plaintext = decrypt_field(encrypted)
        except Exception:
            continue
        config["webhook_secret"] = plaintext
        config.pop("webhook_secret_enc", None)
        bind.execute(
            sa.text(
                """
                UPDATE delivery_schedules
                SET config = CAST(:config_json AS jsonb), updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": row["id"], "config_json": json.dumps(config)},
        )


def _downgrade_external_connection_secrets() -> None:
    bind = op.get_bind()

    # Controlled rollback path (to be removed after migration freeze window).
    op.execute(drop_trigger_sql("external_connections"))
    try:
        rows = bind.execute(
            sa.text(
                """
                SELECT id, secret_ref
                FROM external_connections
                WHERE secret_ref IS NOT NULL
                  AND secret_ref <> ''
                """
            )
        ).mappings()
        for row in rows:
            encrypted = str(row["secret_ref"] or "").strip()
            if not encrypted:
                continue
            try:
                plaintext = decrypt_field(encrypted)
            except Exception:
                continue
            bind.execute(
                sa.text(
                    """
                    UPDATE external_connections
                    SET secret_ref = :secret_ref
                    WHERE id = :id
                    """
                ),
                {"id": row["id"], "secret_ref": plaintext},
            )
    finally:
        op.execute(create_trigger_sql("external_connections"))


def upgrade() -> None:
    if _table_exists("delivery_schedules"):
        _upgrade_delivery_webhook_secrets()
    if _table_exists("external_connections"):
        _upgrade_external_connection_secrets()


def downgrade() -> None:
    if _table_exists("delivery_schedules"):
        _downgrade_delivery_webhook_secrets()
    if _table_exists("external_connections"):
        _downgrade_external_connection_secrets()
