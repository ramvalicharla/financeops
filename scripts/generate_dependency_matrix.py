from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
OUTPUT_FILE = ROOT / "DEPENDENCY_MATRIX.md"


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _normalise_python_dep(dep: str) -> tuple[str, str]:
    match = re.match(r"^\s*([A-Za-z0-9_.\-]+)(\[.*?\])?\s*([<>=!~].+)?\s*$", dep)
    if not match:
        return dep.strip(), "unknown"
    name = (match.group(1) or "").strip()
    constraint = (match.group(3) or "").strip()
    if not constraint:
        return name, "unknown"
    version = constraint
    for token in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if token in constraint:
            version = constraint.split(token, 1)[1].strip()
            break
    return name, version or "unknown"


def parse_python_deps() -> list[dict[str, str]]:
    pyproject_path = BACKEND_DIR / "pyproject.toml"
    if not pyproject_path.exists():
        return []
    try:
        content = tomllib.loads(_safe_read_text(pyproject_path))
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    project = content.get("project", {})
    for dep in project.get("dependencies", []):
        name, version = _normalise_python_dep(str(dep))
        if name:
            rows.append({"name": name, "version": version, "ecosystem": "python"})

    optional = project.get("optional-dependencies", {})
    for _, deps in optional.items():
        for dep in deps:
            name, version = _normalise_python_dep(str(dep))
            if name:
                rows.append({"name": name, "version": version, "ecosystem": "python"})

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["name"].lower()
        existing = deduped.get(key)
        if existing is None or existing["version"] == "unknown":
            deduped[key] = row
    return sorted(deduped.values(), key=lambda item: item["name"].lower())


def parse_node_deps() -> list[dict[str, str]]:
    package_path = FRONTEND_DIR / "package.json"
    if not package_path.exists():
        return []
    try:
        pkg = json.loads(_safe_read_text(package_path))
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    for section in ("dependencies", "devDependencies"):
        for name, version in pkg.get(section, {}).items():
            rows.append(
                {
                    "name": str(name),
                    "version": str(version).lstrip("^~"),
                    "ecosystem": "node",
                }
            )

    deduped: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row["name"].lower()
        if key not in deduped:
            deduped[key] = row
    return sorted(deduped.values(), key=lambda item: item["name"].lower())


def parse_system_deps() -> list[dict[str, str]]:
    dockerfile_path = BACKEND_DIR / "Dockerfile"
    if not dockerfile_path.exists():
        return []
    body = _safe_read_text(dockerfile_path)
    packages: set[str] = set()
    capture = False
    buffer = ""
    for line in body.splitlines():
        stripped = line.strip()
        if "apt-get install" in stripped:
            capture = True
            buffer = stripped
        elif capture:
            buffer += f" {stripped}"
        if capture and not stripped.endswith("\\"):
            capture = False
            cleaned = buffer.replace("\\", " ").replace("&&", " ")
            for token in cleaned.split():
                if token.startswith("-"):
                    continue
                if token in {"apt-get", "install", "update", "rm", "mkdir", "echo"}:
                    continue
                if "/" in token or token.startswith("$"):
                    continue
                if token and token.isascii():
                    packages.add(token)
            buffer = ""
    return [{"name": name, "version": "n/a", "ecosystem": "system"} for name in sorted(packages)]


def _http_json(url: str, timeout: float = 1.5) -> dict | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "financeops-dependency-matrix/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return None


def _internet_available() -> bool:
    if os.getenv("DEPENDENCY_MATRIX_SKIP_NETWORK", "false").lower() in {"1", "true", "yes"}:
        return False
    probe = _http_json("https://pypi.org/pypi/pip/json", timeout=1.0)
    return probe is not None


def _python_latest_and_meta(package_name: str) -> tuple[str, str, str]:
    payload = _http_json(f"https://pypi.org/pypi/{urllib.parse.quote(package_name)}/json")
    if payload is None:
        return "not_checked", "not_checked", "not_checked"
    info = payload.get("info", {})
    latest_version = str(info.get("version") or "unknown")
    license_name = str(info.get("license") or "unknown")
    last_updated = "unknown"
    releases = payload.get("releases", {})
    if isinstance(releases, dict):
        candidates = releases.get(latest_version, [])
        if isinstance(candidates, list) and candidates:
            uploaded = candidates[0].get("upload_time_iso_8601") or candidates[0].get("upload_time")
            if uploaded:
                last_updated = str(uploaded)
    return latest_version, license_name, last_updated


def _node_latest_and_meta(package_name: str) -> tuple[str, str, str]:
    encoded_name = urllib.parse.quote(package_name, safe="@/")
    payload_latest = _http_json(f"https://registry.npmjs.org/{encoded_name}/latest")
    if payload_latest is None:
        return "not_checked", "not_checked", "not_checked"
    latest_version = str(payload_latest.get("version") or "unknown")
    license_name = str(payload_latest.get("license") or "unknown")
    payload_full = _http_json(f"https://registry.npmjs.org/{encoded_name}")
    if payload_full is None:
        return latest_version, license_name, "unknown"
    time_map = payload_full.get("time", {})
    last_updated = str(time_map.get(latest_version) or time_map.get("modified") or "unknown")
    return latest_version, license_name, last_updated


def _security_status(ecosystem: str, package_name: str) -> str:
    if ecosystem not in {"python", "node"}:
        return "not_checked"
    return "not_checked"


def enrich_dependencies(rows: list[dict[str, str]], network_enabled: bool) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []
    for row in rows:
        latest_version = "not_checked"
        license_name = "not_checked"
        last_updated = "not_checked"
        if network_enabled:
            if row["ecosystem"] == "python":
                latest_version, license_name, last_updated = _python_latest_and_meta(row["name"])
            elif row["ecosystem"] == "node":
                latest_version, license_name, last_updated = _node_latest_and_meta(row["name"])

        enriched.append(
            {
                **row,
                "latest_version": latest_version,
                "license": license_name,
                "security_status": _security_status(row["ecosystem"], row["name"]),
                "last_updated": last_updated,
            }
        )
    return enriched


def _render_table(title: str, rows: list[dict[str, str]]) -> list[str]:
    lines = [f"## {title}", "", "| Package | Current Version | Latest Version | License | Security Status | Last Updated |", "|---|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            "| {name} | {version} | {latest} | {license} | {security} | {updated} |".format(
                name=row["name"],
                version=row["version"],
                latest=row.get("latest_version", "not_checked"),
                license=row.get("license", "not_checked"),
                security=row.get("security_status", "not_checked"),
                updated=row.get("last_updated", "not_checked"),
            )
        )
    if not rows:
        lines.append("| — | — | — | — | — | — |")
    lines.append("")
    return lines


def generate_matrix() -> str:
    python_rows = parse_python_deps()
    node_rows = parse_node_deps()
    system_rows = parse_system_deps()

    network_enabled = _internet_available()
    python_rows = enrich_dependencies(python_rows, network_enabled=network_enabled)
    node_rows = enrich_dependencies(node_rows, network_enabled=network_enabled)

    lines: list[str] = [
        "# Dependency Matrix",
        "",
        f"Generated: {date.today().isoformat()}",
        f"Network metadata lookup: {'enabled' if network_enabled else 'disabled'}",
        f"Python packages: {len(python_rows)}",
        f"Node packages: {len(node_rows)}",
        f"System packages: {len(system_rows)}",
        "",
    ]
    lines.extend(_render_table("Python Dependencies (Backend)", python_rows))
    lines.extend(_render_table("Node Dependencies (Frontend)", node_rows))
    lines.extend(_render_table("System Dependencies (Dockerfile)", system_rows))
    lines.extend(
        [
            "## Notes",
            "- This file is auto-generated by `scripts/generate_dependency_matrix.py`.",
            "- Do not edit manually.",
            "- In offline CI, latest version/license/security fields degrade to `not_checked`.",
            "",
            "## Security",
            "- Run `pip-audit` for Python CVEs.",
            "- Run `npm audit` for Node CVEs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        content = generate_matrix()
        OUTPUT_FILE.write_text(content, encoding="utf-8")
        print(f"Generated: {OUTPUT_FILE}")
        print(f"Lines: {len(content.splitlines())}")
        return 0
    except Exception as exc:  # noqa: BLE001
        fallback = (
            "# Dependency Matrix\n\n"
            f"Generated: {date.today().isoformat()}\n\n"
            f"Generation failed gracefully: {exc}\n"
        )
        try:
            OUTPUT_FILE.write_text(fallback, encoding="utf-8")
            print(f"Generated fallback: {OUTPUT_FILE}")
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
