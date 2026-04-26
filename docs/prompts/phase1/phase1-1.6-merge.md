# Claude Code Prompt — Merge Phase 1 Sub-Prompt 1.6 to main

> **Context:** Sub-prompt 1.6 (route migration + /settings/team consolidation) is complete on `feat/phase1-route-migration` with 4 internal commits across 5 verified checkpoints.

## Paste this into Claude Code

```
git status                                                # expect clean
git branch --show-current                                 # expect feat/phase1-route-migration
git log --oneline ^main feat/phase1-route-migration       # should show 4 commits (1.6.1–1.6.4)
git log --oneline main -1                                 # capture pre-merge main HEAD

git checkout main
git merge --no-ff feat/phase1-route-migration -m "Merge branch 'feat/phase1-route-migration' into main

Phase 1 sub-prompt 1.6 — route migration + /settings/team consolidation.

4 internal commits, each independently verifiable via the branch's checkpoint
discipline:

- 1.6.1: /modules → /settings/modules (with permanent redirect)
- 1.6.2: /billing → /settings/billing AND /audit → /governance/audit
         (with permanent redirects)
- 1.6.3: /settings/team consolidated page (shadcn Tabs, ?tab= URL state).
         /settings/users and /settings/groups are now thin redirect pages
         that send users to /settings/team?tab=users (or ?tab=groups)
- 1.6.4: nav-config.ts updated — Modules, Billing · Credits, Audit trail,
         and Team · RBAC now point at canonical paths. 4 TODO Phase 2
         comments removed.

User-visible: 7 of 12 sidebar nav items now navigate to working routes
(was 3 of 12 before 1.6). The remaining 5 (Today's focus, Period close,
Approvals, Connectors, Compliance) still placeholder pending Phase 2/6.

Audit IA-correctness: all spec §1.3 sidebar paths now match real Next.js
routes. Pre-onboarding readiness substantially improved.

Tag handling: v4.3.0-phase1-complete preserved as the structural milestone.
v4.3.1 will be created post-merge as the usable-routes milestone."

If merge produces conflicts, STOP, run `git merge --abort`, report.

cd frontend
npm run typecheck                # 0 errors required
npm run lint 2>&1 | tail -5      # 0 NEW errors
npm run test 2>&1 | tail -10     # baseline failures only (5 known)
npm run build 2>&1 | tail -25    # clean build, route count matches expectations

# Sanity check the topology
git log --oneline --graph -15 main

Expected near top:
*   {merge}      Merge branch 'feat/phase1-route-migration' into main
|\
| * {commit-d}   feat(shell): phase 1.6.4 — sidebar nav-config...
| * {commit-c}   feat(settings): phase 1.6.3 — consolidate...
| * {commit-b}   refactor(routes): phase 1.6.2 — move /billing and /audit...
| * {commit-a}   refactor(routes): phase 1.6.1 — move /modules to...
|/
*   b8c3aa1      Merge branch 'chore/phase1-exit-gate' into main
... (rest of Phase 1 history)

# Smoke check the redirects existence
grep -A 3 "/modules" frontend/next.config.* 2>/dev/null | head -20

## Tag v4.3.1

After verifying clean build, tag:

git tag -a v4.3.1 -m "Phase 1 — Shell with usable routes

Builds on v4.3.0-phase1-complete (structural shell) by migrating sidebar nav
items to canonical routes per spec §1.3.

Sub-prompts on top of v4.3.0:
- 1.6.1 — /modules → /settings/modules
- 1.6.2 — /billing → /settings/billing, /audit → /governance/audit
- 1.6.3 — /settings/users + /settings/groups consolidated into /settings/team
          with shadcn Tabs and ?tab= URL state
- 1.6.4 — nav-config.ts updated to canonical paths

User impact:
- 7 of 12 sidebar items now navigate to working pages (was 3 of 12)
- Old paths preserved via permanent redirects for bookmark compatibility
- Spec §1.3 IA correctness achieved for all available routes

Remaining placeholders (5 items) require Phase 2 (Today's focus, Period close,
Approvals + their backend data sources) and Phase 6 (Connectors, Compliance).

Backward-compatible: all old URLs (/modules, /billing, /audit, /settings/users,
/settings/groups) remain reachable via 307 redirects."

git tag --list "v4*"             # confirm v4.3.1 present alongside v4.3.0-phase1-complete

## Final report

1. Pre-merge main HEAD
2. Merge commit hash
3. Post-merge main HEAD
4. Tag created (verbatim git tag --list)
5. typecheck / lint / test / build verbatim
6. Topology verbatim
7. Total commits between v4.3.0-phase1-complete and v4.3.1
8. git status clean, did NOT push main, did NOT push tag

DO NOT push. Final push decision is the user's.
```

---

## After Claude Code reports merge done

You'll have:
- main updated with the 1.6 merge commit
- 4 commits on the branch lane preserved in `--no-ff` topology
- `v4.3.0-phase1-complete` and `v4.3.1` both present locally
- Nothing pushed to origin

The push decision waits for your explicit instruction. When you push, both tags should go up:

```
git push origin main
git push origin v4.3.0-phase1-complete
git push origin v4.3.1
```
