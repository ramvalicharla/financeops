# Phase 1F.2 Reconciliation Bridge DB Closure Checklist

## Migration
- [x] Fresh Postgres migration to head succeeds (`0013_phase1f2_recon_bridge`).
- [x] Reconciliation bridge tables created with constraints and indexes.

## RLS
- [x] RLS ENABLE + FORCE on all reconciliation bridge tables.
- [x] Cross-tenant read/insert denied in DB-backed tests.

## Append-only
- [x] Update attempts rejected on reconciliation lines/events/evidence tables.
- [x] Resolution and evidence are append-event based.

## Determinism
- [x] Session token deterministic for same inputs.
- [x] Repeated run on same session idempotent and stable.
- [x] GL vs TB deterministic.
- [x] MIS vs TB deterministic.

## Control Plane
- [x] Context token required.
- [x] Module enablement enforced (`reconciliation_bridge`).
- [x] RBAC permissions enforced.
- [x] Tenant-scoped access preserved.

## Isolation
- [x] No writes to accounting engine schedule tables.
- [x] No writes to journal tables.
- [x] No FX side effects.
