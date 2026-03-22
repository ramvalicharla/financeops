from __future__ import annotations

from financeops.services.accounting_common.lineage_contract import (
    LineageMetadata,
    build_lineage_metadata,
    validate_lineage_chain,
)
from financeops.services.accounting_common.run_base_models import (
    RunCreateResult,
    RunStatusSnapshot,
)
from financeops.services.accounting_common.run_events_base import (
    RUN_EVENT_ACCEPTED,
    RUN_EVENT_COMPLETED,
    RUN_EVENT_COMPLETED_WITH_WARNINGS,
    RUN_EVENT_FAILED,
    RUN_EVENT_RUNNING,
    TERMINAL_EVENT_TYPES,
)
from financeops.services.accounting_common.run_lifecycle import (
    append_event,
    create_run_header,
    derive_latest_status,
    ensure_idempotent_event,
    validate_lineage_before_finalize,
)
from financeops.services.accounting_common.run_signature import build_request_signature
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    resolve_terminal_node,
    validate_linear_chain,
)

__all__ = [
    "LineageMetadata",
    "RUN_EVENT_ACCEPTED",
    "RUN_EVENT_COMPLETED",
    "RUN_EVENT_COMPLETED_WITH_WARNINGS",
    "RUN_EVENT_FAILED",
    "RUN_EVENT_RUNNING",
    "RunCreateResult",
    "RunStatusSnapshot",
    "TERMINAL_EVENT_TYPES",
    "append_event",
    "build_lineage_metadata",
    "build_request_signature",
    "create_run_header",
    "derive_latest_status",
    "ensure_idempotent_event",
    "ensure_append_targets_terminal",
    "resolve_terminal_node",
    "SupersessionNode",
    "validate_lineage_before_finalize",
    "validate_lineage_chain",
    "validate_linear_chain",
]

