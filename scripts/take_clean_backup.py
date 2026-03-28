from __future__ import annotations

import fnmatch
import os
import shutil
from datetime import datetime
from pathlib import Path


SOURCE_ROOT = Path(r"D:\finos")
BACKUP_PARENT = Path(r"D:\\")

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".next",
    "venv",
    ".venv",
    "volumes",
    ".claude",
    ".git",
    "workbench",
    "dist",
    "build",
    ".turbo",
    "htmlcov",
}
EXCLUDED_RELATIVE_DIRS = {
    Path("frontend/out"),
}
EXCLUDED_FILE_PATTERNS = (
    "*.pyc",
    ".env",
    ".env.*",
    "*.env",
    "*.sqlite",
    "*.log",
    ".DS_Store",
    "*.sock",
    ".coverage",
)


def _format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def _is_excluded_dir(rel_dir: Path) -> bool:
    if not rel_dir.parts:
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in rel_dir.parts):
        return True
    return rel_dir in EXCLUDED_RELATIVE_DIRS


def _is_excluded_file(rel_file: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in rel_file.parts):
        return True
    if any(rel_file.parent == excluded for excluded in EXCLUDED_RELATIVE_DIRS):
        return True
    name = rel_file.name
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_FILE_PATTERNS)


def _collect_files(src_root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root_str, dir_names, file_names in os.walk(src_root, topdown=True):
        current_root = Path(current_root_str)
        rel_root = current_root.relative_to(src_root)
        filtered_dirs: list[str] = []
        for dir_name in dir_names:
            rel_dir = rel_root / dir_name
            if not _is_excluded_dir(rel_dir):
                filtered_dirs.append(dir_name)
        dir_names[:] = filtered_dirs

        for file_name in file_names:
            rel_file = rel_root / file_name
            if _is_excluded_file(rel_file):
                continue
            files.append(rel_file)
    return files


def _verify_exclusions(dst_root: Path) -> list[str]:
    violations: list[str] = []
    for path in dst_root.rglob("*"):
        rel_path = path.relative_to(dst_root)
        if path.is_dir():
            if _is_excluded_dir(rel_path):
                violations.append(str(rel_path))
            continue
        if _is_excluded_file(rel_path):
            violations.append(str(rel_path))
    return violations


def main() -> None:
    if not SOURCE_ROOT.exists():
        raise RuntimeError(f"Source path does not exist: {SOURCE_ROOT}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = BACKUP_PARENT / f"finos_backup_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=False)

    files_to_copy = _collect_files(SOURCE_ROOT)
    total_size = 0
    for rel_file in files_to_copy:
        src_file = SOURCE_ROOT / rel_file
        dst_file = backup_root / rel_file
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        total_size += src_file.stat().st_size

    top_level_folders = sorted(
        path.name for path in backup_root.iterdir() if path.is_dir()
    )
    violations = _verify_exclusions(backup_root)

    print(f"Backup location: {backup_root}")
    print(f"Total files copied: {len(files_to_copy)}")
    print(f"Total size copied: {_format_size(total_size)}")
    print("Top-level folders included:")
    for folder in top_level_folders:
        print(f"  - {folder}")

    if violations:
        print("Excluded pattern check: FAILED")
        print("Found excluded paths in backup output:")
        for violation in violations[:50]:
            print(f"  - {violation}")
    else:
        print("Excluded pattern check: PASSED (no excluded patterns found)")


if __name__ == "__main__":
    main()
