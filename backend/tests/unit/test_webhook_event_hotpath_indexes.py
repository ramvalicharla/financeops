from __future__ import annotations

from financeops.db.models.payment import WebhookEvent


def test_webhook_event_hotpath_indexes_preserve_global_dedupe_and_retention_scan() -> None:
    index_names = {index.name for index in WebhookEvent.__table__.indexes}
    unique_constraint_names = {
        constraint.name
        for constraint in WebhookEvent.__table__.constraints
        if getattr(constraint, "name", None)
    }

    assert "idx_webhook_events_tenant" in index_names
    assert "idx_webhook_events_created_at" in index_names
    assert "uq_webhook_events_provider_event" in unique_constraint_names
