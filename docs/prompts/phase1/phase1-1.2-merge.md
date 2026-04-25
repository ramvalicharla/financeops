# Claude Code Prompt — Merge Phase 1 Sub-Prompt 1.2 to main

> **Context:** 1.2 (TopBar verify + landmark cleanup + FU-011 + FU-012) complete on `feat/phase1-topbar-verify-cleanup`.

## Paste this into Claude Code

```
git status
git branch --show-current
git log --oneline -1
git log --oneline ^main feat/phase1-topbar-verify-cleanup
git log --oneline main -1

git checkout main
git merge --no-ff feat/phase1-topbar-verify-cleanup -m "Merge branch 'feat/phase1-topbar-verify-cleanup' into main

Phase 1 sub-prompt 1.2 — TopBar verification, landmark cleanup, follow-up filing.

- TopBar verified: 48px height, FY chip, OrgSwitcher, CommandPalette,
  NotificationBell, user avatar all in place from QW batch
- Duplicate <main> landmark sweep complete
- FU-011 filed (brand mark, deferred from Phase 1 by user direction)
- FU-012 filed (sidebar behavioral wiring, deferred from 1.1)
- INDEX.md updated"

If conflicts: STOP, run `git merge --abort`, report.

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -20

git log --oneline --graph -8 main

Report:
1. Pre-merge main HEAD
2. 1.2 merge commit hash
3. Post-merge main HEAD
4. typecheck / lint / build verbatim
5. Topology
6. git status clean, did NOT push
```

After merge, run `phase1-1.3-module-icons.md`.
