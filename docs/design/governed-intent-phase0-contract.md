# Governed Intent Adapter Contract

## Phase 0 Reality

The frontend journal UI uses `createGovernedIntent()` from [intents.ts](/d:/finos/frontend/lib/api/intents.ts)
as the only allowed mutation adapter.

## Why this exists

Phase 0 requires:

- intent-first execution in frontend UX
- no direct mutation helper usage in UI
- non-blocking control-plane behavior

However, the current backend does **not** expose a mounted generic:

- `POST /api/v1/platform/control-plane/intents`

What it does expose today are governed journal endpoints that already return intent metadata:

- `POST /api/v1/accounting/journals/`
- `POST /api/v1/accounting/journals/{id}/submit`
- `POST /api/v1/accounting/journals/{id}/review`
- `POST /api/v1/accounting/journals/{id}/approve`
- `POST /api/v1/accounting/journals/{id}/post`
- `POST /api/v1/accounting/journals/{id}/reverse`

## Frontend rule

UI code must call only:

- `createGovernedIntent()`

Legacy journal mutation helpers remain exported only for backward compatibility and they now throw immediately if used.

## Explicit Mapping

The mapping is explicit inside [intents.ts](/d:/finos/frontend/lib/api/intents.ts):

- `CREATE_JOURNAL` -> `POST /api/v1/accounting/journals/`
- `SUBMIT_JOURNAL` -> `POST /api/v1/accounting/journals/{id}/submit`
- `REVIEW_JOURNAL` -> `POST /api/v1/accounting/journals/{id}/review`
- `APPROVE_JOURNAL` -> `POST /api/v1/accounting/journals/{id}/approve`
- `POST_JOURNAL` -> `POST /api/v1/accounting/journals/{id}/post`
- `REVERSE_JOURNAL` -> `POST /api/v1/accounting/journals/{id}/reverse`

## Non-blocking rule

Frontend opens the intent panel immediately after backend acceptance and refetches asynchronously.

Frontend must not wait for execution completion in the click path.
