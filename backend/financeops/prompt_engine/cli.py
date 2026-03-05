from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys

from financeops.prompt_engine.dependency_graph import DependencyGraph
from financeops.prompt_engine.executor import PromptExecutionEngine
from financeops.prompt_engine.prompt_loader import PromptLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finos-engine", description="FINOS Prompt Execution Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run prompt execution pipeline")
    run_parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    run_parser.add_argument(
        "--catalog",
        default="docs/prompts/PROMPTS_CATALOG.md",
        help="Prompt catalog path relative to project root",
    )
    run_parser.add_argument(
        "--ledger",
        default="docs/ledgers/PROMPTS_LEDGER.md",
        help="Prompt ledger path relative to project root",
    )
    run_parser.add_argument(
        "--max-rework-attempts",
        type=int,
        default=3,
        help="Maximum rework attempts per prompt",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print dependency-resolved execution order without executing prompts",
    )
    run_parser.add_argument(
        "--runner",
        choices=("codex", "local", "none"),
        default=None,
        help=(
            "Prompt execution backend. "
            "If omitted, FINOS_PROMPT_RUNNER env var is used; defaults to none."
        ),
    )

    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )


def run_pipeline(args: argparse.Namespace) -> int:
    repo_root = _resolve_repo_root(args.project_root)
    backend_root = repo_root / "backend"
    catalog_path = _resolve_cli_path(
        raw_path=args.catalog,
        repo_root=repo_root,
        invocation_cwd=Path.cwd(),
    )
    ledger_path = _resolve_ledger_path(raw_path=args.ledger, repo_root=repo_root)

    if args.dry_run:
        catalog = PromptLoader(catalog_path).load()
        order = DependencyGraph(catalog.prompts).topological_order()
        print("Execution Order:")
        print()
        for idx, prompt in enumerate(order, start=1):
            print(f"{idx}. {prompt.prompt_id} {prompt.subsystem}")
        return 0

    try:
        runner_mode = _resolve_runner_mode(args.runner)
    except ValueError as exc:
        logging.error("%s", exc)
        return 2

    runner_callback = None
    if runner_mode == "local":
        from financeops.prompt_engine.runners.local_runner import (
            build_local_runner_callback,
        )

        runner_callback = build_local_runner_callback(backend_root)
    elif runner_mode == "codex":
        from financeops.prompt_engine.runners.codex_runner import (
            build_codex_runner_callback,
        )

        runner_callback = build_codex_runner_callback(repo_root)

    engine = PromptExecutionEngine(
        project_root=repo_root,
        catalog_path=catalog_path,
        ledger_path=ledger_path,
        runner_callback=runner_callback,
        max_rework_attempts=args.max_rework_attempts,
    )
    summary = engine.run()

    logging.info("Execution summary: total=%d skipped=%d success=%d halted=%s failed_prompt=%s",
                 summary.total_prompts, summary.skipped_success, summary.executed_success,
                 summary.halted_by_stop_file, summary.failed_prompt_id)

    if summary.failed_prompt_id:
        return 1
    return 0


def _resolve_runner_mode(cli_value: str | None) -> str:
    if cli_value is not None:
        return cli_value

    env_value = os.getenv("FINOS_PROMPT_RUNNER", "").strip().lower()
    if not env_value:
        return "none"
    if env_value in {"codex", "local", "none"}:
        return env_value
    raise ValueError(
        f"Unsupported FINOS_PROMPT_RUNNER value: {env_value}. "
        "Supported values: codex, local, none."
    )


def _resolve_repo_root(raw_project_root: str) -> Path:
    candidate = Path(raw_project_root).resolve()
    module_repo_root = Path(__file__).resolve().parents[3]
    normalized_raw = raw_project_root.strip()

    if (candidate / "backend" / "financeops").exists() and (candidate / "docs").exists():
        return candidate
    if normalized_raw not in {"", "."} and (candidate / "docs").exists():
        return candidate
    if (
        candidate.name == "backend"
        and (candidate / "financeops").exists()
        and (candidate.parent / "docs").exists()
    ):
        return candidate.parent
    if candidate == module_repo_root or candidate == module_repo_root / "backend":
        return module_repo_root
    return module_repo_root


def _resolve_cli_path(*, raw_path: str, repo_root: Path, invocation_cwd: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()

    repo_candidate = (repo_root / path).resolve()
    cwd_candidate = (invocation_cwd / path).resolve()

    if repo_candidate.exists():
        return repo_candidate
    if cwd_candidate.exists():
        return cwd_candidate
    return repo_candidate


def _resolve_ledger_path(*, raw_path: str, repo_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (repo_root / path).resolve()


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return run_pipeline(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
