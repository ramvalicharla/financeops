from __future__ import annotations

import logging
import os
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from financeops.observability.logging import configure_logging

log = logging.getLogger(__name__)
configure_logging()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _alembic_config():
    from alembic.config import Config

    backend_root = _backend_root()
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return cfg


def _lock_path() -> Path:
    raw = os.getenv("MIGRATION_LOCK_FILE", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (_backend_root() / ".migration.lock").resolve()


@contextmanager
def _acquire_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        payload = f"pid={os.getpid()} started_at={int(time.time())}\n"
        os.write(fd, payload.encode("utf-8"))
        yield
    except FileExistsError as exc:
        raise RuntimeError(
            f"migration lock already exists at '{path}'. "
            "Another migration run may be in progress."
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                log.warning("failed to remove migration lock file: %s", path)


def run_migrations_to_head() -> str:
    try:
        from alembic import command
        from alembic.script import ScriptDirectory
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Alembic is not installed in the active Python environment. "
            "Install backend dependencies and retry."
        ) from exc

    cfg = _alembic_config()
    script_dir = ScriptDirectory.from_config(cfg)
    head_revision = script_dir.get_current_head() or "<unknown>"
    started = time.perf_counter()
    lock_file = _lock_path()

    log.info("starting alembic upgrade head")
    log.info("migration lock file: %s", lock_file)
    with _acquire_lock(lock_file):
        command.upgrade(cfg, "head")

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    log.info("alembic upgrade head completed in %sms (head=%s)", elapsed_ms, head_revision)
    return head_revision


def main() -> int:
    try:
        head = run_migrations_to_head()
        print(f"Migrations applied successfully. Head={head}")
        return 0
    except Exception as exc:
        log.error("migration run failed: %s", exc)
        traceback.print_exc()
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.stderr.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
