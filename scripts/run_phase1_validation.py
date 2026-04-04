from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def _run_script(script_name: str) -> dict[str, Any]:
    script_path = REPO_ROOT / "scripts" / script_name
    if not script_path.exists():
        return {
            "script": script_name,
            "status": "missing",
            "returncode": None,
            "stdout": "",
            "stderr": f"{script_path} not found",
        }

    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "script": script_name,
        "status": "pass" if proc.returncode == 0 else "fail",
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _load_artifact(filename: str) -> dict[str, Any] | None:
    path = ARTIFACTS_DIR / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    execution_plan = [
        ("validate_migration_run.py", "migration_validation.json"),
        ("e2e_platform_validation.py", "e2e_validation.json"),
        ("validate_webhook_flow.py", "webhook_validation.json"),
        ("validate_tenant_isolation.py", "tenant_validation.json"),
    ]

    runs: list[dict[str, Any]] = []
    for script_name, artifact_name in execution_plan:
        result = _run_script(script_name)
        artifact_payload = _load_artifact(artifact_name)
        result["artifact"] = artifact_name
        result["artifact_payload"] = artifact_payload
        runs.append(result)

    overall_pass = all(item["status"] == "pass" for item in runs)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": overall_pass,
        "validations": runs,
        "summary": {
            "total": len(runs),
            "passed": sum(1 for item in runs if item["status"] == "pass"),
            "failed": sum(1 for item in runs if item["status"] != "pass"),
        },
    }

    report_path = ARTIFACTS_DIR / "phase1_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"artifact": str(report_path), "passed": overall_pass}, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
