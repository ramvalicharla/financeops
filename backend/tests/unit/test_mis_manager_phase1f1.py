from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest

from financeops.db.append_only import APPEND_ONLY_TABLES
from financeops.modules.mis_manager.application.canonical_dictionary_service import (
    CanonicalDictionaryService,
)
from financeops.modules.mis_manager.application.drift_detection_service import (
    DriftDetectionService,
)
from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.domain.invariants import (
    SupersessionNode,
    enforce_engine_isolation,
    enforce_linear_supersession,
)
from financeops.modules.mis_manager.domain.value_objects import (
    SnapshotTokenInput,
    VersionTokenInput,
)
from financeops.modules.mis_manager.infrastructure.token_builder import (
    build_snapshot_token,
    build_version_token,
)


def test_version_token_generation_is_deterministic() -> None:
    template_id = uuid.uuid4()
    payload = VersionTokenInput(
        template_id=template_id,
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        column_signature_hash="d" * 64,
        detection_summary_json={"sheet": "pnl", "row": 1},
    )
    assert build_version_token(payload) == build_version_token(payload)


def test_snapshot_token_generation_is_deterministic() -> None:
    template_version_id = uuid.uuid4()
    payload = SnapshotTokenInput(
        source_file_hash="a" * 64,
        sheet_name="Sheet1",
        structure_hash="b" * 64,
        mapping_set_identity="mapping-v1",
        validation_rule_set_identity="rules-v1",
        reporting_period=date(2026, 1, 31),
        template_version_id=template_version_id,
        status="pending",
    )
    assert build_snapshot_token(payload) == build_snapshot_token(payload)


def test_supersession_linear_enforcement_accepts_linear_chain() -> None:
    template_id = uuid.uuid4()
    a = uuid.uuid4()
    b = uuid.uuid4()
    c = uuid.uuid4()
    nodes = [
        SupersessionNode(id=a, template_id=template_id, supersedes_id=None),
        SupersessionNode(id=b, template_id=template_id, supersedes_id=a),
        SupersessionNode(id=c, template_id=template_id, supersedes_id=b),
    ]
    enforce_linear_supersession(nodes)


def test_supersession_cycle_rejected() -> None:
    template_id = uuid.uuid4()
    a = uuid.uuid4()
    b = uuid.uuid4()
    nodes = [
        SupersessionNode(id=a, template_id=template_id, supersedes_id=b),
        SupersessionNode(id=b, template_id=template_id, supersedes_id=a),
    ]
    with pytest.raises(ValueError, match="cycle"):
        enforce_linear_supersession(nodes)


def test_supersession_branch_rejected() -> None:
    template_id = uuid.uuid4()
    a = uuid.uuid4()
    b = uuid.uuid4()
    c = uuid.uuid4()
    nodes = [
        SupersessionNode(id=a, template_id=template_id, supersedes_id=None),
        SupersessionNode(id=b, template_id=template_id, supersedes_id=a),
        SupersessionNode(id=c, template_id=template_id, supersedes_id=a),
    ]
    with pytest.raises(ValueError, match="branch"):
        enforce_linear_supersession(nodes)


def test_drift_detection_minor_vs_major() -> None:
    svc = DriftDetectionService()

    minor = svc.classify(
        prior_header_hash="h1",
        prior_row_signature_hash="r1",
        prior_column_signature_hash="c1",
        prior_structure_hash="s1",
        candidate_header_hash="h2",
        candidate_row_signature_hash="r1",
        candidate_column_signature_hash="c1",
        candidate_structure_hash="s2",
    )
    assert minor.is_material is False

    major = svc.classify(
        prior_header_hash="h1",
        prior_row_signature_hash="r1",
        prior_column_signature_hash="c1",
        prior_structure_hash="s1",
        candidate_header_hash="h1",
        candidate_row_signature_hash="r2",
        candidate_column_signature_hash="c2",
        candidate_structure_hash="s3",
    )
    assert major.is_material is True


def test_canonical_row_mapping_is_stable() -> None:
    mapping_service = MappingService(CanonicalDictionaryService())
    labels = ["Revenue Net", "Marketing Expense", "Unknown Label"]
    first = mapping_service.map_rows_to_canonical_metrics(labels)
    second = mapping_service.map_rows_to_canonical_metrics(labels)
    assert first == second


def test_normalized_line_generation_is_deterministic() -> None:
    mapping_service = MappingService(CanonicalDictionaryService())
    snapshot_service = SnapshotService(mapping_service)
    headers = ["Metric", "Period_2026_01"]
    rows = [["Revenue Net", "1000"], ["Marketing Expense", "200"]]

    first = snapshot_service.normalize_sheet(
        sheet_name="Sheet1",
        headers=headers,
        rows=rows,
        currency_code="USD",
    )
    second = snapshot_service.normalize_sheet(
        sheet_name="Sheet1",
        headers=headers,
        rows=rows,
        currency_code="USD",
    )
    assert first.normalized_lines == second.normalized_lines
    assert first.validation_summary_json == second.validation_summary_json


def test_no_engine_table_mutation_invariant() -> None:
    with pytest.raises(ValueError, match="cannot write"):
        enforce_engine_isolation("revenue_schedules")


def test_exception_table_registered_as_append_only() -> None:
    assert "mis_ingestion_exceptions" in APPEND_ONLY_TABLES


def test_migration_contains_rls_enforcement_blocks() -> None:
    migration_text = "migrations/versions/0012_phase1f1_mis_manager.py"
    content = Path(migration_text).read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in content
    assert "mis_data_snapshots" in content
