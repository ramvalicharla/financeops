# Phase 1F.6 Invariants

## Determinism
- Same tenant/org/period/source-run set/definition-version set/status yields the same `run_token`.
- Repeated execute against the same created run is idempotent (no duplicate anomaly rows for the completed run).
- Result ordering is deterministic (`line_no`, then stable ids).
- Signals, rollforwards, and evidence are returned with deterministic ordering.

## Governance
- All 1F.6 tables are append-only enforced via central append-only trigger.
- All 1F.6 tables have RLS ENABLE + FORCE.
- Tenant policy is enforced by `tenant_id = current_setting('app.current_tenant_id', true)::uuid`.
- All endpoints are control-plane gated and fail closed.

## Supersession
- Self-supersession is rejected.
- Cross-code supersession is rejected.
- Supersession branching is rejected.
- One-active partial unique indexes prevent ambiguous active definitions/rules.

## Statistical Layer
- Rolling windows limited to deterministic rule-set values (3/6/12/24).
- `z_score` is deterministic and rejects zero-std baselines.
- Regime-shift checks are deterministic and based only on stored historical sequences.
- Seasonal and benchmark fields are schema-supported as deterministic hooks.

## Isolation
- 1F.6 does not mutate normalization outputs, reconciliation outputs, ratio/variance outputs, or risk outputs.
- 1F.6 does not mutate accounting engines.
- 1F.6 does not create journals.
- 1F.6 does not invoke FX side-effects.
