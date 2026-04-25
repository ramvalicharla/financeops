# Claude Code Prompt — Merge Phase 1 Sub-Prompt 1.1 to main

> **Context:** Phase 1 sub-prompt 1.1 (sidebar structural rebuild — 220px, three nav groups) is complete on `feat/phase1-sidebar-structure`.
>
> **No push. No conflict resolution without instructions.**
>
> **Expected runtime:** ~5 minutes.

---

## Paste this into Claude Code

```
## Task: Merge feat/phase1-sidebar-structure into main with full verification

## Pre-flight

git status                                                # expect clean
git branch --show-current                                 # expect feat/phase1-sidebar-structure
git log --oneline -1                                      # capture branch HEAD
git log --oneline ^main feat/phase1-sidebar-structure     # expect 1 commit (or count noted at end of 1.1)
git log --oneline main -1                                 # capture pre-merge main HEAD

If working tree shows changes to TRACKED files, STOP and report.

## Merge

git checkout main
git merge --no-ff feat/phase1-sidebar-structure -m "Merge branch 'feat/phase1-sidebar-structure' into main

Phase 1 sub-prompt 1.1 — sidebar structural rebuild.

- Sidebar width 220px; collapsed rail 52px — matches spec §1.3, §1.4
- Three collapsible nav groups: Workspace / Org / Governance
- Nav config extracted to components/layout/sidebar/nav-config.ts
- 12 nav items total across 3 groups
- Group collapse state is local (Phase 4 will persist server-side)
- Placeholder routes for items where Next.js route doesn't exist yet,
  marked TODO Phase 2

Resolves audit findings #4, #11, #12.
Deferred behavioral wiring (badges, RBAC filter, real routes) tracked
as FU-012 (filed in sub-prompt 1.2)."

If the merge produces conflicts, STOP, run `git merge --abort`, and report files + hunks. Do not attempt resolution.

## Post-merge verification

cd frontend
npm run typecheck                     # 0 errors required
npm run lint 2>&1 | tail -5           # 0 new errors; pre-existing warnings allowed
npm run build 2>&1 | tail -20         # clean build, route count matches Phase 0 exit

Report:
- The verbatim "Compiled successfully" line or equivalent
- The verbatim route count line from build output

## Topology check

git log --oneline --graph -8 main

Expected top of log:
1. Merge commit for sub-prompt 1.1
2. fa3a89a (Phase 0 exit hash, or whatever main was before this merge)
3. ...

## Final report

1. Pre-merge main HEAD hash
2. 1.1 merge commit hash
3. Post-merge main HEAD hash
4. typecheck / lint / build results (verbatim)
5. Topology output
6. git status clean
7. Confirm: did NOT push

If anything fails, do not push, do not force, stop and report.
```

---

## After merge

Once Claude Code reports clean merge and clean build:
1. Review the merge commit hash.
2. Decide on push timing (Phase 0 pushed at exit gate; same pattern works here, or push per-merge if you prefer earlier visibility).
3. Run the next sub-prompt: `phase1-1.2-topbar-cleanup.md`.
