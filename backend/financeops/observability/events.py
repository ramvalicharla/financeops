from __future__ import annotations

# Request lifecycle
REQUEST_START = "request_start"
REQUEST_END = "request_end"
REQUEST_ERROR = "request_error"

# Async jobs / workflows
TASK_START = "task_start"
TASK_SUCCESS = "task_success"
TASK_FAILURE = "task_failure"
WORKFLOW_STARTED = "workflow_started"
WORKFLOW_COMPLETED = "workflow_completed"
WORKFLOW_FAILED = "workflow_failed"

# Critical operations
WEBHOOK_RECEIVED = "webhook_received"
WEBHOOK_PROCESSED = "webhook_processed"
WEBHOOK_FAILED = "webhook_failed"
MIGRATION_STATE_MISMATCH = "migration_state_mismatch"
AUTH_FAILURE = "auth_failure"
ENTITLEMENT_DENIED = "entitlement_denied"
APPEND_ONLY_VIOLATION = "append_only_violation"

