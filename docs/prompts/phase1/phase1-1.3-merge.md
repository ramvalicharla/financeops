# Claude Code Prompt — Merge Phase 1 Sub-Prompt 1.3 to main

## Paste this into Claude Code

```
git status
git branch --show-current
git log --oneline -1
git log --oneline ^main feat/phase1-module-icons
git log --oneline main -1

git checkout main
git merge --no-ff feat/phase1-module-icons -m "Merge branch 'feat/phase1-module-icons' into main

Phase 1 sub-prompt 1.3 — module icon registry + 40px tab container.

- MODULE_ICON_MAP and getModuleIcon() factor module → icon out of ModuleTabs
- Tab strip container fixed at h-10 (40px) per spec §1.5
- ModuleTabs uses registry; safe fallback for unknown workspace_keys
- Active tab style (#185FA5 2px underline) preserved from QW-1

Resolves audit finding #20 and Risk #3."

If conflicts: STOP, abort, report.

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -20

git log --oneline --graph -8 main

Report:
1. Pre-merge main HEAD
2. 1.3 merge commit hash
3. Post-merge main HEAD
4. typecheck / lint / build verbatim
5. Topology
6. git status clean, did NOT push
```

After merge, run `phase1-1.4-metadata-sweep.md`.
