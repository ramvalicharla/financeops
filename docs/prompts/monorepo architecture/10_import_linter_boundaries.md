# PROMPT 10 — ADD IMPORT-LINTER & ENFORCE MODULE BOUNDARIES

**Sprint:** 4 (Architectural Hardening)
**Audit findings closed:** #9, partial #10
**Risk level:** LOW (tooling addition; existing violations get an allowlist)
**Estimated effort:** S-M (1 week)
**Prerequisite:** Prompts 01-09 complete

---

## CONTEXT

Repo root: `D:\finos`
Target additions:
- `D:\finos\backend\.importlinter` (new)
- `D:\finos\backend\pyproject.toml` (add dep)
- `D:\finos\.github\workflows\ci.yml` (add lint step)

The audit found that there's no enforced import-boundary tool. Modules import each other's `application/` and `infrastructure/` internals directly, which:
- Couples modules tightly (rename one module → break others)
- Makes monorepo discipline depend entirely on developer memory
- Will get exponentially worse as module count grows

This prompt adds the tool, defines the contracts, and locks in current boundaries — without forcing a massive refactor today. New violations get blocked; existing violations get an explicit allowlist with a sunset date.

This is the cheapest, highest-leverage architectural fix in the entire backlog.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Survey current module structure
1. List every module under `D:\finos\backend\financeops\modules\`
2. For each module, list its sub-folders (`api/`, `application/`, `domain/`, `infrastructure/`, `schemas/`)
3. Run cross-import scans:
   ```
   rg -n "from financeops\.modules\.(\w+)\.(application|infrastructure|domain)" D:\finos\backend\financeops\modules
   ```
4. Tabulate all cross-module imports of internal layers — this becomes the allowlist baseline

### Step 2 — Define the contracts
Create `D:\finos\backend\.importlinter` with these contracts:

```ini
[importlinter]
root_packages =
    financeops

[importlinter:contract:1]
name = Modules cannot import each other's internals
type = forbidden
source_modules =
    financeops.modules.*
forbidden_modules =
    financeops.modules.*.application.*
    financeops.modules.*.infrastructure.*
    financeops.modules.*.domain.internal.*
ignore_imports =
    # baseline — populate from Step 1 scan; each entry must have an issue/sunset date
    financeops.modules.foo.api -> financeops.modules.bar.application.service  # ISSUE-NNN, sunset YYYY-MM-DD

[importlinter:contract:2]
name = API layer cannot import infrastructure
type = layers
layers =
    financeops.api
    financeops.modules.*.api
    financeops.modules.*.application
    financeops.modules.*.domain
    financeops.modules.*.infrastructure

[importlinter:contract:3]
name = Domain layer is pure (no SQLAlchemy, no FastAPI)
type = forbidden
source_modules =
    financeops.modules.*.domain
forbidden_modules =
    sqlalchemy
    fastapi
    pydantic
ignore_imports =
    # pydantic allowed in domain ONLY for value objects — list explicit exceptions
```

Adjust contract list based on your actual layering — these are starting points.

### Step 3 — Add the dependency
Update `D:\finos\backend\pyproject.toml`:
- Add `import-linter` to dev dependencies
- Pin to a specific version

### Step 4 — Run baseline scan
```
cd D:\finos\backend
lint-imports
```

Capture every violation. Categorize:
- **Trivial fix (XS effort, do now):** rename or move imports — fix immediately in this prompt
- **Architectural fix (M+ effort):** add to `ignore_imports` allowlist with comment + sunset date

### Step 5 — Add CI enforcement
Update `D:\finos\.github\workflows\ci.yml` to add a job:

```yaml
- name: Import boundary check
  run: |
    cd backend
    lint-imports
```

This must FAIL the build on new violations. Existing allowlisted violations don't fail.

### Step 6 — Document the policy
Create `D:\finos\docs\engineering\MODULE_BOUNDARIES.md`:
- Why we have boundaries
- The contract layer rules (with diagrams)
- How to add a new exception (must include issue number + sunset date)
- How to clear an exception (refactor + remove from allowlist)
- Quarterly review process for the allowlist

### Step 7 — Quick wins
For trivial-fix violations from step 4, fix them inline:
- If module A's API uses module B's service via direct import, refactor to call B's API or introduce a shared `packages/` interface
- Do NOT batch architectural refactors here — those are their own prompts

Limit: do not spend more than 2 days on quick-win refactors in this prompt. Anything that takes longer goes to the allowlist with a sunset date.

---

## DO NOT DO

- Do NOT auto-refactor every violation — many require domain knowledge to fix correctly
- Do NOT delete the allowlist — it's the safety valve
- Do NOT skip the sunset date on any allowlist entry
- Do NOT enforce import-linter on test files (they legitimately reach across boundaries to set up state)
- Do NOT add this to frontend in the same prompt — that's a separate ESLint config

---

## VERIFICATION CHECKLIST

- [ ] `import-linter` installed and runs locally
- [ ] `.importlinter` file defines at least 2 contracts
- [ ] Baseline scan shows zero NEW violations (all existing ones are explicitly allowlisted)
- [ ] Every allowlist entry has an ISSUE-NNN and sunset date
- [ ] CI step runs and would fail on a new violation (test by deliberately adding a violation in a draft PR)
- [ ] `MODULE_BOUNDARIES.md` exists
- [ ] Existing tests still pass

---

## FOLLOW-UP TRACKER

After this prompt, create one GitHub issue per allowlisted violation:
- Title: `Refactor: remove import boundary exception <module> -> <module>`
- Sunset date matches the `.importlinter` comment
- Tag: `tech-debt`, `module-boundaries`

Schedule quarterly review to clear at least N entries per quarter.

---

## COMMIT MESSAGE

```
feat(arch): enforce module import boundaries via import-linter

- Added .importlinter with 3 contracts (cross-module internals, layer order, domain purity)
- Baseline allowlist with sunset dates for existing violations
- CI now blocks new boundary violations
- Documented policy in docs/engineering/MODULE_BOUNDARIES.md

Closes audit finding #9. Partially closes finding #10.
Provides the discipline scaffold for the monorepo as module count grows.
```
