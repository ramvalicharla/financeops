# Phase 2.5 Ownership Consolidation Invariants

## Hard invariants
- Append-only across all Phase 2.5 tables.
- RLS + FORCE RLS enabled on all Phase 2.5 tables.
- Deterministic run tokens and deterministic result ordering.
- Supersession-only versioning for structure/rule definition tables.
- No supersession branching, self-supersession, or supersession cycles.
- Ownership relationship cycle rejection.
- No implicit ownership weighting in non-ownership paths.
- No implicit minority-interest treatment without explicit ownership rules/relationships.
- No journal creation, no accounting engine invocation, no upstream mutation.

## Fail-closed conditions
- Missing active ownership structure/rules/minority rules for the run period.
- Missing active ownership relationships for selected structure.
- Missing source consolidation runs.
- Invalid source references.
- Invalid relationship percentages (outside 0..100).
- Referenced FX run not found when supplied.

## Lineage invariants
- Every attributed metric/variance stores source result references in lineage JSON.
- Evidence links preserve rule-version and source reference traceability.
- Optional FX run linkage is explicit and append-only.
