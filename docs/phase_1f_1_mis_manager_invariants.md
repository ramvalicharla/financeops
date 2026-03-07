# MIS Manager Invariants (Phase 1F.1)

1. Append-only persistence for MIS version/snapshot/line/exception/drift/dictionary tables.
2. Template versions are immutable and linked by linear supersession only.
3. Supersession rejects: self-link, cross-template link, branch, cycle.
4. Snapshot records are immutable; validation/finalization produce new status-specific snapshots.
5. No silent drift acceptance for material layout changes.
6. Deterministic hashing for structure/version/snapshot identities.
7. Canonical metric/dimension vocabulary is versioned and append-only.
8. Control-plane + module token enforcement on all MIS endpoints.
9. RLS ENABLE + FORCE with tenant isolation policy on every Phase 1F.1 table.
10. MIS module is engine-isolated and cannot mutate accounting engine tables.
