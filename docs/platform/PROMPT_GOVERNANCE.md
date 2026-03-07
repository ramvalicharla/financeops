# Prompt Governance

## Risk Levels

- `LOW`: routine prompt changes with constrained impact.
- `MEDIUM`: standard engineering prompts (default when catalog risk is missing).
- `HIGH`: sensitive prompts requiring explicit operator approval.

## Catalog Schema

Prompt entries are validated with these fields:

- `prompt_id`
- `title`
- `risk` (`LOW|MEDIUM|HIGH`)
- `description`
- `acceptance_criteria`
- `files_expected` (optional)

Backward compatibility:

- Legacy catalog rows are still accepted.
- Missing `risk` defaults to `MEDIUM` with warning.

## Approval Policy

HIGH risk prompts are blocked unless run with:

```bash
python -m financeops.prompt_engine.cli run --approve-high-risk
```

Optional:

```bash
--approval-token <token>
```

## Dependency Escalation

If patch includes dependency files, the run must include:

- `--allow-deps`
- `--approve-high-risk`

Without these, execution fails closed.

## Review Gate

The deterministic review gate is pluggable and disabled by default.

Enable with:

```bash
--enable-review-gate
```

Current rule-based checks include:

- path scope re-validation
- security-sensitive prompt-engine edits require high-risk approval
- test deletion blocked without high-risk approval
- CI test-disable pattern detection
