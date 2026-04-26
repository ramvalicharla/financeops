# FINQOR — POST-AUDIT EXECUTION SPRINTS

**Source audit:** Codex audit, 50 findings (8 CRITICAL, 29 HIGH, 13 MEDIUM)
**Repo:** `D:\finos`
**Backend:** `D:\finos\backend`
**Frontend:** `D:\finos\frontend`

---

## SPRINT OVERVIEW

| Sprint | Theme | Prompts | Findings Addressed | Duration | Blocks Launch? |
|---|---|---|---|---|---|
| 1 | Security & Integrity | 01, 02, 03, 04 | #1, #2, #3, #4, #5 | Week 1 | YES — all must close before public launch |
| 2 | Operational Unblock | 05, 06 | #6, #7 | Week 2 | YES |
| 3 | Finance Correctness | 07, 08 | #15, #16, #29, partial #17 | Week 3-4 | YES for finance integrity |
| 4 | Architectural Hardening | 09, 10 | #8, #9, partial #10, #13 | Week 4-6 | NO — but blocks enterprise sales |

---

## EXECUTION RULES

1. **Run prompts in order.** Do not skip ahead. Each prompt assumes prior prompts are complete.
2. **One prompt per Codex/Claude Code session.** Do not chain.
3. **Verify before moving on.** Every prompt ends with a verification checklist. If verification fails, stop and debug — do not start the next prompt.
4. **Commit after each prompt.** Use the suggested commit message at the end of each prompt. This gives you clean rollback points.
5. **Path prefix is mandatory** — every prompt re-states `D:\finos` paths because Codex sometimes drifts.
6. **No scope creep.** If Codex tries to "also fix" something not in the prompt, reject and continue with scope only.

---

## PROMPT INVENTORY

| # | File | Sprint | Title | Risk |
|---|---|---|---|---|
| 01 | `01_secrets_purge.md` | 1 | Remove checked-in secrets and rotate | HIGH — git history rewrite |
| 02 | `02_db_tls_runtime.md` | 1 | Restore DB TLS verification (runtime) | LOW |
| 03 | `03_db_tls_migrations.md` | 1 | Restore DB TLS verification (migrations) | LOW |
| 04 | `04_float_to_decimal.md` | 1 | Fix float() in journal balance guard | LOW |
| 05 | `05_alembic_heads_unblock.md` | 2 | Restore `alembic heads` operability | LOW |
| 06 | `06_rls_session_hardening.md` | 2 | Harden public-route session/RLS context | MEDIUM |
| 07 | `07_month_end_close_hardstop.md` | 3 | Month-end close hard-stop on step failure | MEDIUM |
| 08 | `08_audit_columns_currency.md` | 3 | Enforce audit columns + currency derivation | MEDIUM |
| 09 | `09_platform_org_user_split.md` | 4 | Split PlatformUser from OrgUser identity | HIGH — schema change |
| 10 | `10_import_linter_boundaries.md` | 4 | Add import-linter and module boundaries | LOW |

---

## DEPENDENCY ORDER (DO NOT REORDER)

```
01 (secrets) ──┐
02 (TLS rt) ───┼──> CRITICAL Tier A done
03 (TLS mig) ──┤
04 (float) ────┘
       ↓
05 (alembic) ──> 06 (RLS) ──> CRITICAL Tier B done
       ↓
07 (month-end) ──> 08 (audit cols + currency) ──> Finance correctness done
       ↓
09 (user split) ──> 10 (import-linter) ──> Architectural hardening done
```

## KILL-SWITCH CRITERIA

Stop the sprint chain and revisit plan if any of these happen:

- Sprint 1 reveals secrets that were committed to public branches → escalate to security incident response, do not continue with sprint 2 until rotation confirmed
- Sprint 2 RLS hardening reveals tenant data leak in production logs → halt, do forensic review
- Sprint 3 month-end close fix reveals existing customers have partially-closed periods in production → halt, write data remediation plan first
- Sprint 4 user split migration affects more than ~3 production tables → escalate, plan a maintenance window

---

## SUCCESS DEFINITION

After all 10 prompts:

- [ ] Zero CRITICAL findings remain (verify by re-running the audit prompt)
- [ ] All 8 originally-CRITICAL items have an evidence link to a closing commit
- [ ] CI passes on main with no skips
- [ ] `alembic heads` returns exactly one head
- [ ] Import-linter passes (no boundary violations)
- [ ] Pre-launch security checklist green
