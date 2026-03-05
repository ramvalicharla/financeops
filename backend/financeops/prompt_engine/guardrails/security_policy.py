from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "override system prompt",
    "developer message override",
    "jailbreak",
)

FILESYSTEM_ESCAPE_PATTERNS = (
    "../",
    "..\\",
    "/etc/",
    "c:\\windows\\",
)

EXTERNAL_COMMAND_PATTERNS = (
    "curl ",
    "wget ",
    "invoke-webrequest",
    "powershell -",
    "bash -c",
    "cmd.exe",
)

AI_FIREWALL_PATTERNS = (
    "rm -rf",
    "os.system",
    "subprocess",
    "exec(",
    "eval(",
)

SECRET_ACCESS_PATTERNS = (
    "os.environ",
    "dotenv",
    "openai_api_key",
    "aws_secret_access_key",
    "anthropic_api_key",
)

PROTECTED_PATH_GLOBS = (
    ".env",
    ".env.*",
    "requirements.txt",
    "migrations/*",
    "docs/ledgers/*",
)

PROMPTS_LEDGER_PATH = "docs/ledgers/PROMPTS_LEDGER.md"


def normalize_rel_path(path: str | Path) -> str:
    text = str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if text.startswith("/"):
        text = text[1:]
    return PurePosixPath(text).as_posix()


def is_path_protected(rel_path: str) -> bool:
    rel = normalize_rel_path(rel_path).lower()
    for pattern in PROTECTED_PATH_GLOBS:
        if fnmatch.fnmatch(rel, pattern.lower()):
            return True
    return False
