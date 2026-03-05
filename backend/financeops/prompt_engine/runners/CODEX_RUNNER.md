# Codex Runner

`CodexRunner` is a prompt-engine backend that executes prompts through the Codex CLI and applies returned patches with `git apply`.

## Execution Flow

1. Prompt Engine passes `prompt_text` to Codex CLI over stdin.
2. Codex output is parsed for unified diff patch content.
3. Patch paths are validated:
   - Allowed roots: `backend/`, `docs/`, `tests/`
   - Blocked: `infra/`, `docker/`, `.git`, `.env*`, absolute paths, path traversal
4. Patch is applied with:
   - `git apply --whitespace=nowarn --recount -`
5. Runner returns `PromptRunResult`.

## CLI Usage

```bash
python -m financeops.prompt_engine.cli run --catalog ../docs/prompts/PROMPTS_CATALOG.md --runner codex
```

Environment override:

```bash
FINOS_PROMPT_RUNNER=codex
```

Optional custom Codex command:

```bash
FINOS_CODEX_COMMAND="codex exec --output-format patch --stdin"
```

## Notes

- Runner is callback-compatible with `PromptExecutorCallback`.
- Runner does not directly edit files; it only applies patch text via `git apply`.
- Existing pipeline guardrails remain in effect after patch application.
