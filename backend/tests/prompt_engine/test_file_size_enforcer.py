from __future__ import annotations

from pathlib import Path

from financeops.prompt_engine.guardrails.file_size_enforcer import FileSizeEnforcer


def test_file_size_enforcer_flags_large_files(tmp_path: Path) -> None:
    target = tmp_path / "large_module.py"
    target.write_text("\n".join(["x = 1"] * 501), encoding="utf-8")

    enforcer = FileSizeEnforcer(tmp_path, max_file_lines=500)
    result = enforcer.enforce(["large_module.py"])

    assert result.ok is False
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.lines == 501
    assert "service_module" in violation.split_suggestion

