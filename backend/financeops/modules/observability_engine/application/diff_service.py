from __future__ import annotations

from typing import Any


class DiffService:
    def compare(self, *, base: dict[str, Any], compare: dict[str, Any]) -> dict[str, Any]:
        base_versions = dict(base.get("version_tokens", {}))
        compare_versions = dict(compare.get("version_tokens", {}))
        version_keys = sorted(set(base_versions.keys()) | set(compare_versions.keys()))
        version_diffs = [
            {
                "key": key,
                "base": base_versions.get(key),
                "compare": compare_versions.get(key),
            }
            for key in version_keys
            if base_versions.get(key) != compare_versions.get(key)
        ]

        base_deps = list(base.get("dependencies", []))
        compare_deps = list(compare.get("dependencies", []))
        dep_drift = base_deps != compare_deps

        drift_flag = bool(base.get("run_token") != compare.get("run_token") or version_diffs or dep_drift)
        return {
            "base": {
                "module_code": base.get("module_code"),
                "run_id": str(base.get("run_id")),
                "run_token": base.get("run_token"),
            },
            "compare": {
                "module_code": compare.get("module_code"),
                "run_id": str(compare.get("run_id")),
                "run_token": compare.get("run_token"),
            },
            "run_token_equal": base.get("run_token") == compare.get("run_token"),
            "version_token_diffs": version_diffs,
            "dependency_diff": dep_drift,
            "drift_flag": drift_flag,
        }
