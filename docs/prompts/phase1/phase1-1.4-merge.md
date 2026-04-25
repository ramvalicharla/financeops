# Claude Code Prompt — Merge Phase 1 Sub-Prompt 1.4 to main

## Paste this into Claude Code

```
git status
git branch --show-current
git log --oneline -1
git log --oneline ^main feat/phase1-metadata-sweep
git log --oneline main -1

git checkout main
git merge --no-ff feat/phase1-metadata-sweep -m "Merge branch 'feat/phase1-metadata-sweep' into main

Phase 1 sub-prompt 1.4 — route metadata sweep.

- export const metadata or generateMetadata added to remaining
  dashboard pages
- Title format: '{Page} · Finqor'
- Per-page descriptions one-line, route-purpose aligned

Resolves audit finding #25 residual scope.
Spec ref §1.8 item 6."

If conflicts: STOP, abort, report.

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -20

git log --oneline --graph -8 main

Report:
1. Pre-merge main HEAD
2. 1.4 merge commit hash
3. Post-merge main HEAD
4. typecheck / lint / build verbatim
5. Topology
6. git status clean, did NOT push
```

After merge, run `phase1-1.5-exit-gate.md`.
