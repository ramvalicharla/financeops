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
        choices=("local", "none"),
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
    root = Path(args.project_root).resolve()
    if args.dry_run:
        catalog = PromptLoader(root / args.catalog).load()
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

        runner_callback = build_local_runner_callback(root)

    engine = PromptExecutionEngine(
        project_root=root,
        catalog_path=root / args.catalog,
        ledger_path=root / args.ledger,
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
    if env_value in {"local", "none"}:
        return env_value
    raise ValueError(
        f"Unsupported FINOS_PROMPT_RUNNER value: {env_value}. "
        "Supported values: local, none."
    )


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
