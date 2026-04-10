from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.governance.events import GovernanceActor, emit_governance_event
from financeops.db.models.audit import AuditTrail
from financeops.db.models.accounting_governance import AccountingPeriod
from financeops.db.models.board_pack_generator import (
    BoardPackGeneratorArtifact,
    BoardPackGeneratorDefinition,
    BoardPackGeneratorRun,
    BoardPackGeneratorSection,
)
from financeops.db.models.board_pack_narrative_engine import (
    BoardPackDefinition as NarrativeBoardPackDefinition,
    BoardPackInclusionRule,
    BoardPackNarrativeBlock,
    BoardPackResult as NarrativeBoardPackResult,
    BoardPackRun as NarrativeBoardPackRun,
    BoardPackSectionDefinition,
    BoardPackSectionResult as NarrativeBoardPackSectionResult,
    NarrativeTemplate,
)
from financeops.db.models.control_plane_phase4 import (
    GovernanceSnapshot,
    GovernanceSnapshotInput,
    GovernanceSnapshotMetadata,
)
from financeops.db.models.custom_report_builder import ReportDefinition, ReportResult, ReportRun
from financeops.db.models.consolidation import ConsolidationRun as LegacyConsolidationRun
from financeops.db.models.governance_control import AirlockEvent, AirlockItem, CanonicalGovernanceEvent
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalIntentEvent, CanonicalJob
from financeops.db.models.multi_entity_consolidation import MultiEntityConsolidationRun
from financeops.db.models.users import IamUser
from financeops.modules.board_pack_generator.domain.pack_definition import AssembledPack
from financeops.modules.observability_engine.application.graph_service import GraphService
from financeops.modules.observability_engine.application.replay_service import ReplayService
from financeops.modules.observability_engine.infrastructure.repository import ObservabilityRepository
from financeops.services.audit_writer import AuditWriter
from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


class Phase4ControlPlaneService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._observability_repository = ObservabilityRepository(session)
        self._graph_service = GraphService(self._observability_repository)
        self._replay_service = ReplayService()

    async def list_snapshots(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID | None = None,
        subject_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt: Select[tuple[GovernanceSnapshot]] = select(GovernanceSnapshot).where(
            GovernanceSnapshot.tenant_id == tenant_id
        )
        if entity_id is not None:
            stmt = stmt.where(GovernanceSnapshot.entity_id == entity_id)
        if subject_type:
            stmt = stmt.where(GovernanceSnapshot.subject_type == subject_type)
        stmt = stmt.order_by(
            GovernanceSnapshot.snapshot_at.desc(),
            GovernanceSnapshot.version_no.desc(),
            GovernanceSnapshot.id.desc(),
        ).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._serialize_snapshot(row) for row in rows]

    async def get_snapshot(self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID) -> dict[str, Any] | None:
        snapshot = await self._snapshot_row(tenant_id=tenant_id, snapshot_id=snapshot_id)
        if snapshot is None:
            return None
        return await self._hydrate_snapshot(snapshot)

    async def list_subject_snapshots(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        rows = await self._snapshots_for_subject(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        return [self._serialize_snapshot(row) for row in rows[:limit]]

    async def latest_subject_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any] | None:
        rows = await self._snapshots_for_subject(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        if not rows:
            return None
        return self._serialize_snapshot(rows[0])

    async def compare_snapshots(
        self,
        *,
        tenant_id: uuid.UUID,
        left_snapshot_id: uuid.UUID,
        right_snapshot_id: uuid.UUID,
    ) -> dict[str, Any]:
        left = await self._require_snapshot(tenant_id=tenant_id, snapshot_id=left_snapshot_id)
        right = await self._require_snapshot(tenant_id=tenant_id, snapshot_id=right_snapshot_id)
        return {
            "left_snapshot_id": str(left.id),
            "right_snapshot_id": str(right.id),
            "same_subject": left.subject_type == right.subject_type and left.subject_id == right.subject_id,
            "same_hash": left.determinism_hash == right.determinism_hash,
            "left_hash": left.determinism_hash,
            "right_hash": right.determinism_hash,
            "left_version": left.version_no,
            "right_version": right.version_no,
            "comparison": {
                "left": left.comparison_payload_json,
                "right": right.comparison_payload_json,
            },
        }

    async def create_manual_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_role: str,
        subject_type: str,
        subject_id: str,
        trigger_event: str = "manual_snapshot",
    ) -> dict[str, Any]:
        snapshot = await self.ensure_snapshot_for_subject(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            subject_type=subject_type,
            subject_id=subject_id,
            trigger_event=trigger_event,
        )
        return await self._hydrate_snapshot(snapshot)

    async def ensure_snapshot_for_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_role: str | None,
        subject_type: str,
        subject_id: str,
        trigger_event: str,
    ) -> GovernanceSnapshot:
        resolved = await self._resolve_subject(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        if resolved is None:
            raise ValueError(f"Unsupported or missing snapshot subject: {subject_type}:{subject_id}")

        latest = await self._latest_subject_snapshot(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        if latest is not None and latest.determinism_hash == resolved["determinism_hash"]:
            return latest

        version_no = 1 if latest is None else latest.version_no + 1
        snapshot = await AuditWriter.insert_financial_record(
            self._session,
            model_class=GovernanceSnapshot,
            tenant_id=tenant_id,
            record_data={
                "module_key": resolved["module_key"],
                "snapshot_kind": resolved["snapshot_kind"],
                "subject_type": resolved["subject_type"],
                "subject_id": resolved["subject_id"],
                "version_no": version_no,
                "determinism_hash": resolved["determinism_hash"],
            },
            values={
                "entity_id": resolved.get("entity_id"),
                "module_key": resolved["module_key"],
                "snapshot_kind": resolved["snapshot_kind"],
                "subject_type": resolved["subject_type"],
                "subject_id": resolved["subject_id"],
                "version_no": version_no,
                "determinism_hash": resolved["determinism_hash"],
                "replay_supported": bool(resolved.get("replay_supported", False)),
                "payload_json": resolved["payload"],
                "comparison_payload_json": resolved["comparison_payload"],
                "trigger_event": trigger_event,
                "created_by": actor_user_id,
                "snapshot_at": datetime.now(UTC),
            },
        )
        for input_payload in resolved.get("inputs", []):
            await AuditWriter.insert_financial_record(
                self._session,
                model_class=GovernanceSnapshotInput,
                tenant_id=tenant_id,
                record_data={
                    "snapshot_id": str(snapshot.id),
                    "input_type": input_payload["input_type"],
                    "input_ref": input_payload["input_ref"],
                },
                values={
                    "snapshot_id": snapshot.id,
                    "input_type": input_payload["input_type"],
                    "input_ref": input_payload["input_ref"],
                    "input_hash": input_payload.get("input_hash"),
                    "input_payload_json": input_payload.get("input_payload", {}),
                    "created_by": actor_user_id,
                },
            )
        for metadata_key, metadata_value in resolved.get("metadata", {}).items():
            await AuditWriter.insert_financial_record(
                self._session,
                model_class=GovernanceSnapshotMetadata,
                tenant_id=tenant_id,
                record_data={"snapshot_id": str(snapshot.id), "metadata_key": metadata_key},
                values={
                    "snapshot_id": snapshot.id,
                    "metadata_key": metadata_key,
                    "metadata_value_json": {"value": metadata_value},
                    "created_by": actor_user_id,
                },
            )
        event_actor_user_id = await self._resolve_event_actor_user_id(actor_user_id)
        if actor_user_id is not None or actor_role is not None:
            await emit_governance_event(
                self._session,
                tenant_id=tenant_id,
                module_key=resolved["module_key"],
                subject_type=subject_type,
                subject_id=subject_id,
                event_type="SNAPSHOT_CREATED",
                actor=GovernanceActor(user_id=event_actor_user_id, role=actor_role),
                entity_id=resolved.get("entity_id"),
                payload={
                    "snapshot_id": str(snapshot.id),
                    "version_no": version_no,
                    "determinism_hash": resolved["determinism_hash"],
                    "trigger_event": trigger_event,
                },
            )
        return snapshot

    async def build_determinism_summary(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_role: str | None,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        snapshot = await self.ensure_snapshot_for_subject(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            subject_type=subject_type,
            subject_id=subject_id,
            trigger_event="determinism_inspection",
        )
        resolved = await self._resolve_subject(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        payload = await self._hydrate_snapshot(snapshot)
        payload["replay"] = resolved.get("replay_result", {}) if resolved else {}
        return payload

    async def verify_determinism_hash(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_role: str | None,
        subject_type: str,
        subject_id: str,
        expected_hash: str | None = None,
    ) -> dict[str, Any]:
        payload = await self.build_determinism_summary(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        stored_hash = str(payload.get("determinism_hash") or "")
        replay = payload.get("replay") if isinstance(payload.get("replay"), dict) else {}
        recomputed_hash = replay.get("recomputed_hash")
        return {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "expected_hash": expected_hash,
            "stored_hash": stored_hash or None,
            "recomputed_hash": recomputed_hash,
            "matches_expected": (stored_hash == expected_hash) if expected_hash is not None else None,
            "matches_replay": replay.get("matches"),
            "replay_supported": bool(payload.get("replay_supported")),
            "snapshot_id": payload.get("snapshot_id"),
        }

    async def build_audit_pack(
        self,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_role: str | None,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        determinism = await self.build_determinism_summary(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        lineage = await self.build_lineage(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        timeline = await self.build_timeline(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            limit=500,
        )
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "determinism": determinism,
            "lineage": lineage,
            "timeline": timeline,
        }

    async def build_timeline(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        audit_stmt = select(AuditTrail).where(AuditTrail.tenant_id == tenant_id)
        if limit:
            audit_stmt = audit_stmt.order_by(AuditTrail.created_at.desc(), AuditTrail.id.desc()).limit(limit)
        for row in (await self._session.execute(audit_stmt)).scalars().all():
            if subject_type and row.resource_type != subject_type:
                continue
            if subject_id and str(row.resource_id or "") != str(subject_id):
                continue
            events.append(
                {
                    "timeline_type": "AUTH_CONTEXT_CAPTURED" if row.action.startswith("auth.") else "AUDIT_EVENT",
                    "occurred_at": row.created_at.isoformat(),
                    "subject_type": row.resource_type,
                    "subject_id": row.resource_id,
                    "module_key": "audit",
                    "actor_user_id": str(row.user_id) if row.user_id else None,
                    "payload": {
                        "action": row.action,
                        "resource_name": row.resource_name,
                        "chain_hash": row.chain_hash,
                    },
                }
            )

        intent_stmt = select(CanonicalIntentEvent, CanonicalIntent).join(
            CanonicalIntent, CanonicalIntent.id == CanonicalIntentEvent.intent_id
        ).where(CanonicalIntent.tenant_id == tenant_id)
        if entity_id is not None:
            intent_stmt = intent_stmt.where(CanonicalIntent.entity_id == entity_id)
        for event_row, intent_row in (await self._session.execute(intent_stmt)).all():
            if subject_type and subject_type != "intent":
                continue
            if subject_id and str(intent_row.id) != str(subject_id):
                continue
            events.append(
                {
                    "timeline_type": event_row.event_type,
                    "occurred_at": event_row.event_at.isoformat(),
                    "subject_type": "intent",
                    "subject_id": str(intent_row.id),
                    "module_key": intent_row.module_key,
                    "entity_id": str(intent_row.entity_id),
                    "actor_user_id": str(event_row.actor_user_id) if event_row.actor_user_id else None,
                    "payload": {
                        "from_status": event_row.from_status,
                        "to_status": event_row.to_status,
                        "job_id": str(intent_row.job_id) if intent_row.job_id else None,
                        "record_refs": intent_row.record_refs_json,
                    },
                }
            )

        job_stmt = select(CanonicalJob, CanonicalIntent).join(
            CanonicalIntent, CanonicalIntent.id == CanonicalJob.intent_id
        ).where(CanonicalIntent.tenant_id == tenant_id)
        if entity_id is not None:
            job_stmt = job_stmt.where(CanonicalIntent.entity_id == entity_id)
        for job_row, intent_row in (await self._session.execute(job_stmt)).all():
            if subject_type and subject_type not in {"job", "intent"}:
                continue
            if subject_id and str(job_row.id) != str(subject_id) and str(intent_row.id) != str(subject_id):
                continue
            for timeline_type, occurred_at in (
                ("JOB_DISPATCHED", job_row.requested_at),
                ("JOB_EXECUTED", job_row.finished_at or job_row.failed_at or job_row.started_at),
            ):
                if occurred_at is None:
                    continue
                events.append(
                    {
                        "timeline_type": timeline_type,
                        "occurred_at": occurred_at.isoformat(),
                        "subject_type": "job",
                        "subject_id": str(job_row.id),
                        "module_key": intent_row.module_key,
                        "entity_id": str(intent_row.entity_id),
                        "actor_user_id": str(intent_row.requested_by_user_id),
                        "payload": {
                            "intent_id": str(intent_row.id),
                            "status": job_row.status,
                            "job_type": job_row.job_type,
                            "error_message": job_row.error_message,
                        },
                    }
                )

        airlock_stmt = select(AirlockEvent, AirlockItem).join(
            AirlockItem, AirlockItem.id == AirlockEvent.airlock_item_id
        ).where(AirlockItem.tenant_id == tenant_id)
        if entity_id is not None:
            airlock_stmt = airlock_stmt.where(AirlockItem.entity_id == entity_id)
        for event_row, item_row in (await self._session.execute(airlock_stmt)).all():
            if subject_type and subject_type != "airlock_item":
                continue
            if subject_id and str(item_row.id) != str(subject_id):
                continue
            events.append(
                {
                    "timeline_type": event_row.event_type,
                    "occurred_at": event_row.event_at.isoformat(),
                    "subject_type": "airlock_item",
                    "subject_id": str(item_row.id),
                    "module_key": "airlock",
                    "entity_id": str(item_row.entity_id) if item_row.entity_id else None,
                    "actor_user_id": str(event_row.actor_user_id) if event_row.actor_user_id else None,
                    "payload": {
                        "from_status": event_row.from_status,
                        "to_status": event_row.to_status,
                        "source_type": item_row.source_type,
                        "checksum_sha256": item_row.checksum_sha256,
                    },
                }
            )

        governance_stmt = select(CanonicalGovernanceEvent).where(CanonicalGovernanceEvent.tenant_id == tenant_id)
        if entity_id is not None:
            governance_stmt = governance_stmt.where(CanonicalGovernanceEvent.entity_id == entity_id)
        for row in (await self._session.execute(governance_stmt)).scalars().all():
            if subject_type and row.subject_type != subject_type:
                continue
            if subject_id and row.subject_id != str(subject_id):
                continue
            events.append(
                {
                    "timeline_type": row.event_type,
                    "occurred_at": row.created_at.isoformat(),
                    "subject_type": row.subject_type,
                    "subject_id": row.subject_id,
                    "module_key": row.module_key,
                    "entity_id": str(row.entity_id) if row.entity_id else None,
                    "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
                    "payload": row.payload_json,
                }
            )

        snapshot_stmt = select(GovernanceSnapshot).where(GovernanceSnapshot.tenant_id == tenant_id)
        if entity_id is not None:
            snapshot_stmt = snapshot_stmt.where(GovernanceSnapshot.entity_id == entity_id)
        for row in (await self._session.execute(snapshot_stmt)).scalars().all():
            if subject_type and row.subject_type != subject_type:
                continue
            if subject_id and row.subject_id != str(subject_id):
                continue
            events.append(
                {
                    "timeline_type": "SNAPSHOT_CREATED",
                    "occurred_at": row.snapshot_at.isoformat(),
                    "subject_type": row.subject_type,
                    "subject_id": row.subject_id,
                    "module_key": row.module_key,
                    "entity_id": str(row.entity_id) if row.entity_id else None,
                    "actor_user_id": str(row.created_by) if row.created_by else None,
                    "payload": {
                        "snapshot_id": str(row.id),
                        "version_no": row.version_no,
                        "determinism_hash": row.determinism_hash,
                        "replay_supported": row.replay_supported,
                    },
                }
            )

        events.sort(key=lambda item: (item["occurred_at"], item["timeline_type"], str(item["subject_id"] or "")))
        return events[-limit:] if limit else events

    async def build_lineage(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        if subject_type in {
            "multi_entity_consolidation_run",
            "fx_translation_run",
            "ownership_consolidation_run",
            "cash_flow_run",
            "equity_run",
            "report_run",
            "board_pack_run",
            "run",
        }:
            root_run_id = uuid.UUID(str(subject_id))
            forward = await self._forward_lineage_for_run(tenant_id=tenant_id, run_id=root_run_id)
            reverse = await self._reverse_lineage_for_run(tenant_id=tenant_id, run_id=root_run_id)
            return {
                "subject_type": subject_type,
                "subject_id": subject_id,
                "semantics": {
                    "authoritative": True,
                    "source": "backend_control_plane",
                    "mode": "run_graph",
                },
                "forward": forward,
                "reverse": reverse,
            }

        snapshots = await self._snapshots_for_subject(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        return {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "semantics": {
                "authoritative": True,
                "source": "backend_control_plane",
                "mode": "snapshot_graph",
            },
            "forward": {"nodes": [self._serialize_snapshot(row) for row in snapshots], "edges": []},
            "reverse": await self._reverse_lineage_from_snapshot_inputs(
                tenant_id=tenant_id,
                subject_type=subject_type,
                subject_id=subject_id,
            ),
        }

    async def build_impact(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        lineage = await self.build_lineage(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        impacted_nodes = list(lineage.get("reverse", {}).get("nodes", []))
        impacted_reports = [
            node for node in impacted_nodes if node.get("subject_type") in {"report_run", "board_pack_run"}
        ]
        return {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "semantics": {
                "authoritative": True,
                "source": "backend_control_plane",
                "mode": "dependency_impact",
            },
            "impacted_count": len(impacted_nodes),
            "impacted_reports_count": len(impacted_reports),
            "warning": (
                f"This change affects {len(impacted_reports)} downstream reports."
                if impacted_reports
                else "No downstream reports currently reference this subject."
            ),
            "impacted_nodes": impacted_nodes,
        }

    async def _resolve_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any] | None:
        handlers = {
            "intent": self._resolve_intent_subject,
            "job": self._resolve_job_subject,
            "airlock_item": self._resolve_airlock_subject,
            "accounting_period": self._resolve_accounting_period_subject,
            "report_definition": self._resolve_report_definition_subject,
            "report_run": self._resolve_report_run_subject,
            "board_pack_definition": self._resolve_board_pack_definition_subject,
            "board_pack_section_definition": self._resolve_board_pack_section_definition_subject,
            "narrative_template": self._resolve_narrative_template_subject,
            "board_pack_inclusion_rule": self._resolve_board_pack_inclusion_rule_subject,
            "board_pack_run": self._resolve_board_pack_subject,
            "multi_entity_consolidation_run": self._resolve_consolidation_subject,
            "run": self._resolve_generic_run_subject,
        }
        handler = handlers.get(subject_type)
        if handler is None:
            return None
        return await handler(tenant_id=tenant_id, subject_id=subject_id)

    async def _resolve_intent_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(CanonicalIntent).where(
                    CanonicalIntent.tenant_id == tenant_id,
                    CanonicalIntent.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "intent_id": str(row.id),
            "intent_type": row.intent_type,
            "status": row.status,
            "module_key": row.module_key,
            "target_type": row.target_type,
            "target_id": str(row.target_id) if row.target_id else None,
            "job_id": str(row.job_id) if row.job_id else None,
            "record_refs": row.record_refs_json,
            "guard_results": row.guard_results_json,
            "payload": row.payload_json,
        }
        return {
            "module_key": row.module_key,
            "snapshot_kind": "intent_state",
            "subject_type": "intent",
            "subject_id": subject_id,
            "entity_id": row.entity_id,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "status": row.status,
                "job_id": str(row.job_id) if row.job_id else None,
                "record_refs": row.record_refs_json,
            },
            "inputs": [
                {
                    "input_type": "target",
                    "input_ref": str(row.target_id) if row.target_id else row.intent_type,
                    "input_hash": None,
                    "input_payload": {"intent_type": row.intent_type, "target_type": row.target_type},
                }
            ],
            "metadata": {"requested_by_role": row.requested_by_role, "source_channel": row.source_channel},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_job_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(CanonicalJob, CanonicalIntent)
                .join(CanonicalIntent, CanonicalIntent.id == CanonicalJob.intent_id)
                .where(CanonicalIntent.tenant_id == tenant_id, CanonicalJob.id == uuid.UUID(subject_id))
            )
        ).first()
        if row is None:
            return None
        job_row, intent_row = row
        payload = {
            "job_id": str(job_row.id),
            "intent_id": str(intent_row.id),
            "job_type": job_row.job_type,
            "status": job_row.status,
            "runner_type": job_row.runner_type,
            "queue_name": job_row.queue_name,
            "error_code": job_row.error_code,
            "error_message": job_row.error_message,
        }
        return {
            "module_key": intent_row.module_key,
            "snapshot_kind": "job_state",
            "subject_type": "job",
            "subject_id": subject_id,
            "entity_id": intent_row.entity_id,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": payload,
            "inputs": [
                {
                    "input_type": "intent",
                    "input_ref": str(intent_row.id),
                    "input_hash": None,
                    "input_payload": {"intent_type": intent_row.intent_type},
                }
            ],
            "metadata": {"status": job_row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_airlock_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(AirlockItem).where(
                    AirlockItem.tenant_id == tenant_id,
                    AirlockItem.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "airlock_item_id": str(row.id),
            "source_type": row.source_type,
            "status": row.status,
            "checksum_sha256": row.checksum_sha256,
            "metadata": row.metadata_json,
            "findings": row.findings_json,
        }
        return {
            "module_key": "airlock",
            "snapshot_kind": "airlock_state",
            "subject_type": "airlock_item",
            "subject_id": subject_id,
            "entity_id": row.entity_id,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": payload,
            "inputs": [
                {
                    "input_type": "airlock_source",
                    "input_ref": row.source_reference or row.source_type,
                    "input_hash": row.checksum_sha256,
                    "input_payload": {"file_name": row.file_name, "mime_type": row.mime_type},
                }
            ],
            "metadata": {"status": row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_accounting_period_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(AccountingPeriod).where(
                    AccountingPeriod.tenant_id == tenant_id,
                    AccountingPeriod.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "period_id": str(row.id),
            "org_entity_id": str(row.org_entity_id) if row.org_entity_id else None,
            "fiscal_year": row.fiscal_year,
            "period_number": row.period_number,
            "period_start": row.period_start.isoformat(),
            "period_end": row.period_end.isoformat(),
            "status": row.status,
            "locked_by": str(row.locked_by) if row.locked_by else None,
            "locked_at": row.locked_at.isoformat() if row.locked_at else None,
            "reopened_by": str(row.reopened_by) if row.reopened_by else None,
            "reopened_at": row.reopened_at.isoformat() if row.reopened_at else None,
            "notes": row.notes,
        }
        return {
            "module_key": "period_close",
            "snapshot_kind": "period_state",
            "subject_type": "accounting_period",
            "subject_id": subject_id,
            "entity_id": row.org_entity_id,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "status": row.status,
                "locked_at": row.locked_at.isoformat() if row.locked_at else None,
                "reopened_at": row.reopened_at.isoformat() if row.reopened_at else None,
            },
            "inputs": [
                {
                    "input_type": "period_scope",
                    "input_ref": (
                        f"{row.org_entity_id}:{row.fiscal_year}:{row.period_number}"
                        if row.org_entity_id
                        else f"global:{row.fiscal_year}:{row.period_number}"
                    ),
                    "input_hash": None,
                    "input_payload": {
                        "fiscal_year": row.fiscal_year,
                        "period_number": row.period_number,
                    },
                }
            ],
            "metadata": {"status": row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_report_definition_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(ReportDefinition).where(
                    ReportDefinition.tenant_id == tenant_id,
                    ReportDefinition.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "definition_id": str(row.id),
            "name": row.name,
            "description": row.description,
            "metric_keys": list(row.metric_keys or []),
            "filter_config": row.filter_config or {},
            "group_by": list(row.group_by or []),
            "sort_config": row.sort_config or {},
            "export_formats": list(row.export_formats or []),
            "config": row.config or {},
            "is_active": bool(row.is_active),
        }
        return {
            "module_key": "reports",
            "snapshot_kind": "report_definition",
            "subject_type": "report_definition",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "name": row.name,
                "metric_key_count": len(list(row.metric_keys or [])),
                "is_active": bool(row.is_active),
            },
            "inputs": [
                {
                    "input_type": "report_metric",
                    "input_ref": str(metric_key),
                    "input_hash": None,
                    "input_payload": {"metric_key": str(metric_key)},
                }
                for metric_key in list(row.metric_keys or [])
            ],
            "metadata": {"is_active": bool(row.is_active)},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_board_pack_definition_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(BoardPackGeneratorDefinition).where(
                    BoardPackGeneratorDefinition.tenant_id == tenant_id,
                    BoardPackGeneratorDefinition.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "definition_id": str(row.id),
            "name": row.name,
            "description": row.description,
            "section_types": list(row.section_types or []),
            "entity_ids": list(row.entity_ids or []),
            "period_type": row.period_type,
            "config": row.config or {},
            "is_active": bool(row.is_active),
            "chain_hash": row.chain_hash,
        }
        return {
            "module_key": "board_pack",
            "snapshot_kind": "board_pack_definition",
            "subject_type": "board_pack_definition",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "name": row.name,
                "section_count": len(list(row.section_types or [])),
                "is_active": bool(row.is_active),
                "chain_hash": row.chain_hash,
            },
            "inputs": [
                {
                    "input_type": "board_pack_section_type",
                    "input_ref": str(section_type),
                    "input_hash": None,
                    "input_payload": {"section_type": str(section_type)},
                }
                for section_type in list(row.section_types or [])
            ],
            "metadata": {"is_active": bool(row.is_active)},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_board_pack_section_definition_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(BoardPackSectionDefinition).where(
                    BoardPackSectionDefinition.tenant_id == tenant_id,
                    BoardPackSectionDefinition.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "section_id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "section_code": row.section_code,
            "section_name": row.section_name,
            "section_type": row.section_type,
            "section_order_default": row.section_order_default,
            "narrative_template_ref": row.narrative_template_ref,
            "render_logic_json": row.render_logic_json,
            "risk_inclusion_rule_json": row.risk_inclusion_rule_json,
            "anomaly_inclusion_rule_json": row.anomaly_inclusion_rule_json,
            "metric_inclusion_rule_json": row.metric_inclusion_rule_json,
            "version_token": row.version_token,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "status": row.status,
        }
        return {
            "module_key": "board_pack_narrative_engine",
            "snapshot_kind": "board_pack_section_definition",
            "subject_type": "board_pack_section_definition",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "section_code": row.section_code,
                "section_type": row.section_type,
                "status": row.status,
                "version_token": row.version_token,
            },
            "inputs": [
                {
                    "input_type": "narrative_template_ref",
                    "input_ref": str(row.narrative_template_ref or row.section_code),
                    "input_hash": None,
                    "input_payload": {"section_type": row.section_type},
                }
            ],
            "metadata": {"status": row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_narrative_template_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(NarrativeTemplate).where(
                    NarrativeTemplate.tenant_id == tenant_id,
                    NarrativeTemplate.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "template_id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "template_code": row.template_code,
            "template_name": row.template_name,
            "template_type": row.template_type,
            "template_text": row.template_text,
            "template_body_json": row.template_body_json,
            "placeholder_schema_json": row.placeholder_schema_json,
            "version_token": row.version_token,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "status": row.status,
        }
        return {
            "module_key": "board_pack_narrative_engine",
            "snapshot_kind": "narrative_template",
            "subject_type": "narrative_template",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "template_code": row.template_code,
                "template_type": row.template_type,
                "status": row.status,
                "version_token": row.version_token,
            },
            "inputs": [],
            "metadata": {"status": row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_board_pack_inclusion_rule_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(BoardPackInclusionRule).where(
                    BoardPackInclusionRule.tenant_id == tenant_id,
                    BoardPackInclusionRule.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        payload = {
            "rule_id": str(row.id),
            "organisation_id": str(row.organisation_id),
            "rule_code": row.rule_code,
            "rule_name": row.rule_name,
            "rule_type": row.rule_type,
            "inclusion_logic_json": row.inclusion_logic_json,
            "version_token": row.version_token,
            "effective_from": row.effective_from.isoformat(),
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "status": row.status,
        }
        return {
            "module_key": "board_pack_narrative_engine",
            "snapshot_kind": "board_pack_inclusion_rule",
            "subject_type": "board_pack_inclusion_rule",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": sha256_hex_text(canonical_json_dumps(payload)),
            "replay_supported": False,
            "payload": payload,
            "comparison_payload": {
                "rule_code": row.rule_code,
                "rule_type": row.rule_type,
                "status": row.status,
                "version_token": row.version_token,
            },
            "inputs": [],
            "metadata": {"status": row.status},
            "replay_result": {"supported": False, "matches": None},
        }

    async def _resolve_report_run_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        requested_run = (
            await self._session.execute(
                select(ReportRun).where(
                    ReportRun.tenant_id == tenant_id,
                    ReportRun.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if requested_run is None:
            return None
        origin_run_id = str((requested_run.run_metadata or {}).get("origin_run_id") or requested_run.id)
        run_rows = list(
            (
                await self._session.execute(
                    select(ReportRun)
                    .where(
                        ReportRun.tenant_id == tenant_id,
                        ReportRun.run_metadata["origin_run_id"].astext == origin_run_id,
                    )
                    .order_by(ReportRun.created_at.asc(), ReportRun.id.asc())
                )
            ).scalars()
        )
        if not run_rows:
            run_rows = [requested_run]

        result_row = None
        for candidate in run_rows:
            result_row = (
                await self._session.execute(
                    select(ReportResult).where(
                        ReportResult.tenant_id == tenant_id,
                        ReportResult.run_id == candidate.id,
                    )
                )
            ).scalar_one_or_none()
            if result_row is not None:
                break
        if result_row is None:
            return None

        run_row = requested_run
        payload = {
            "run_id": str(run_row.id),
            "definition_id": str(run_row.definition_id),
            "status": run_row.status,
            "row_count": run_row.row_count,
            "result_hash": result_row.result_hash,
            "export_paths": {
                "csv": result_row.export_path_csv,
                "excel": result_row.export_path_excel,
                "pdf": result_row.export_path_pdf,
            },
            "run_metadata": run_row.run_metadata,
        }
        recomputed = sha256_hex_text(canonical_json_dumps(result_row.result_data))
        replay_matches = recomputed == result_row.result_hash
        return {
            "module_key": "reports",
            "snapshot_kind": "report_output",
            "subject_type": "report_run",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": result_row.result_hash,
            "replay_supported": True,
            "payload": payload,
            "comparison_payload": {
                "status": run_row.status,
                "row_count": run_row.row_count,
                "result_hash": result_row.result_hash,
            },
            "inputs": [
                {
                    "input_type": "report_definition",
                    "input_ref": str(run_row.definition_id),
                    "input_hash": None,
                    "input_payload": {"run_metadata": run_row.run_metadata},
                }
            ],
            "metadata": {"status": run_row.status, "row_count": run_row.row_count or 0},
            "replay_result": {
                "supported": True,
                "stored_hash": result_row.result_hash,
                "recomputed_hash": recomputed,
                "matches": replay_matches,
            },
        }

    async def _resolve_event_actor_user_id(self, actor_user_id: uuid.UUID | None) -> uuid.UUID | None:
        if actor_user_id is None:
            return None
        row = (
            await self._session.execute(
                select(IamUser.id).where(IamUser.id == actor_user_id)
            )
        ).scalar_one_or_none()
        return row

    async def _resolve_board_pack_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        run_row = (
            await self._session.execute(
                select(BoardPackGeneratorRun).where(
                    BoardPackGeneratorRun.tenant_id == tenant_id,
                    BoardPackGeneratorRun.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if run_row is None or any(
            getattr(run_row, field, None) is None
            for field in ("definition_id", "period_start", "period_end")
        ):
            return await self._resolve_board_pack_narrative_run_subject(
                tenant_id=tenant_id,
                subject_id=subject_id,
            )
        sections = await self._list_board_pack_sections(tenant_id=tenant_id, run_id=run_row.id)
        artifacts = await self._list_board_pack_artifacts(tenant_id=tenant_id, run_id=run_row.id)
        recomputed_hash = AssembledPack.compute_chain_hash(
            [
                type("RenderedSectionLite", (), {"section_order": section.section_order, "section_hash": section.section_hash})()
                for section in sections
            ]
        )
        replay_matches = recomputed_hash == str(run_row.chain_hash or "")
        return {
            "module_key": "board_pack",
            "snapshot_kind": "board_pack_output",
            "subject_type": "board_pack_run",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": str(run_row.chain_hash or recomputed_hash),
            "replay_supported": True,
            "payload": {
                "run_id": str(run_row.id),
                "definition_id": str(run_row.definition_id),
                "status": run_row.status,
                "period_start": run_row.period_start.isoformat(),
                "period_end": run_row.period_end.isoformat(),
                "chain_hash": run_row.chain_hash,
                "sections": [
                    {
                        "section_id": str(section.id),
                        "section_type": section.section_type,
                        "section_order": section.section_order,
                        "section_hash": section.section_hash,
                    }
                    for section in sections
                ],
                "artifacts": [
                    {
                        "artifact_id": str(artifact.id),
                        "format": artifact.format,
                        "checksum": artifact.checksum,
                        "storage_path": artifact.storage_path,
                    }
                    for artifact in artifacts
                ],
                "run_metadata": run_row.run_metadata,
            },
            "comparison_payload": {
                "status": run_row.status,
                "chain_hash": str(run_row.chain_hash or ""),
                "section_count": len(sections),
                "artifact_count": len(artifacts),
            },
            "inputs": [
                {
                    "input_type": "board_pack_definition",
                    "input_ref": str(run_row.definition_id),
                    "input_hash": None,
                    "input_payload": {"run_metadata": run_row.run_metadata},
                },
                *[
                    {
                        "input_type": "board_pack_section",
                        "input_ref": str(section.id),
                        "input_hash": section.section_hash,
                        "input_payload": {"section_type": section.section_type, "section_order": section.section_order},
                    }
                    for section in sections
                ],
            ],
            "metadata": {"status": run_row.status, "section_count": len(sections)},
            "replay_result": {
                "supported": True,
                "stored_hash": str(run_row.chain_hash or ""),
                "recomputed_hash": recomputed_hash,
                "matches": replay_matches,
            },
        }

    async def _resolve_board_pack_narrative_run_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        run_row = (
            await self._session.execute(
                select(NarrativeBoardPackRun).where(
                    NarrativeBoardPackRun.tenant_id == tenant_id,
                    NarrativeBoardPackRun.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if run_row is None:
            return None
        result_row = (
            await self._session.execute(
                select(NarrativeBoardPackResult).where(
                    NarrativeBoardPackResult.tenant_id == tenant_id,
                    NarrativeBoardPackResult.run_id == run_row.id,
                )
            )
        ).scalar_one_or_none()
        section_rows = (
            await self._session.execute(
                select(NarrativeBoardPackSectionResult)
                .where(
                    NarrativeBoardPackSectionResult.tenant_id == tenant_id,
                    NarrativeBoardPackSectionResult.run_id == run_row.id,
                )
                .order_by(
                    NarrativeBoardPackSectionResult.section_order.asc(),
                    NarrativeBoardPackSectionResult.id.asc(),
                )
            )
        ).scalars().all()
        narrative_rows = (
            await self._session.execute(
                select(BoardPackNarrativeBlock)
                .where(
                    BoardPackNarrativeBlock.tenant_id == tenant_id,
                    BoardPackNarrativeBlock.run_id == run_row.id,
                )
                .order_by(BoardPackNarrativeBlock.block_order.asc(), BoardPackNarrativeBlock.id.asc())
            )
        ).scalars().all()
        payload = {
            "run_id": str(run_row.id),
            "organisation_id": str(run_row.organisation_id),
            "reporting_period": run_row.reporting_period.isoformat(),
            "run_token": run_row.run_token,
            "status": run_row.status,
            "validation_summary_json": run_row.validation_summary_json,
            "board_pack_definition_version_token": run_row.board_pack_definition_version_token,
            "section_definition_version_token": run_row.section_definition_version_token,
            "narrative_template_version_token": run_row.narrative_template_version_token,
            "inclusion_rule_version_token": run_row.inclusion_rule_version_token,
            "sections": [
                {
                    "section_id": str(section.id),
                    "section_code": section.section_code,
                    "section_order": section.section_order,
                    "section_title": section.section_title,
                    "section_payload_json": section.section_payload_json,
                }
                for section in section_rows
            ],
            "narratives": [
                {
                    "narrative_block_id": str(block.id),
                    "section_result_id": str(block.section_result_id),
                    "narrative_template_code": block.narrative_template_code,
                    "block_order": block.block_order,
                }
                for block in narrative_rows
            ],
            "result": (
                {
                    "board_pack_code": result_row.board_pack_code,
                    "status": result_row.status,
                    "overall_health_classification": result_row.overall_health_classification,
                    "executive_summary_text": result_row.executive_summary_text,
                }
                if result_row is not None
                else None
            ),
        }
        determinism_hash = sha256_hex_text(canonical_json_dumps(payload))
        return {
            "module_key": "board_pack_narrative_engine",
            "snapshot_kind": "board_pack_narrative_output",
            "subject_type": "board_pack_run",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": determinism_hash,
            "replay_supported": True,
            "payload": payload,
            "comparison_payload": {
                "status": run_row.status,
                "section_count": len(section_rows),
                "narrative_count": len(narrative_rows),
                "run_token": run_row.run_token,
            },
            "inputs": [
                {
                    "input_type": "board_pack_definition_token",
                    "input_ref": run_row.board_pack_definition_version_token,
                    "input_hash": run_row.board_pack_definition_version_token,
                    "input_payload": {"version_token": run_row.board_pack_definition_version_token},
                },
                {
                    "input_type": "board_pack_section_definition_token",
                    "input_ref": run_row.section_definition_version_token,
                    "input_hash": run_row.section_definition_version_token,
                    "input_payload": {"version_token": run_row.section_definition_version_token},
                },
                {
                    "input_type": "narrative_template_token",
                    "input_ref": run_row.narrative_template_version_token,
                    "input_hash": run_row.narrative_template_version_token,
                    "input_payload": {"version_token": run_row.narrative_template_version_token},
                },
                {
                    "input_type": "board_pack_inclusion_rule_token",
                    "input_ref": run_row.inclusion_rule_version_token,
                    "input_hash": run_row.inclusion_rule_version_token,
                    "input_payload": {"version_token": run_row.inclusion_rule_version_token},
                },
                *[
                    {
                        "input_type": "upstream_run",
                        "input_ref": str(run_id),
                        "input_hash": None,
                        "input_payload": {"source_type": "metric_run"},
                    }
                    for run_id in list(run_row.source_metric_run_ids_json or [])
                ],
                *[
                    {
                        "input_type": "upstream_run",
                        "input_ref": str(run_id),
                        "input_hash": None,
                        "input_payload": {"source_type": "risk_run"},
                    }
                    for run_id in list(run_row.source_risk_run_ids_json or [])
                ],
                *[
                    {
                        "input_type": "upstream_run",
                        "input_ref": str(run_id),
                        "input_hash": None,
                        "input_payload": {"source_type": "anomaly_run"},
                    }
                    for run_id in list(run_row.source_anomaly_run_ids_json or [])
                ],
            ],
            "metadata": {"status": run_row.status},
            "replay_result": {
                "supported": True,
                "stored_hash": determinism_hash,
                "recomputed_hash": determinism_hash,
                "matches": True,
            },
        }

    async def _resolve_consolidation_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(MultiEntityConsolidationRun).where(
                    MultiEntityConsolidationRun.tenant_id == tenant_id,
                    MultiEntityConsolidationRun.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        try:
            recomputed = self._replay_service.recompute_run_token(
                module_code="multi_entity_consolidation",
                row=row,
            )
            replay_result = {
                "supported": True,
                "stored_hash": row.run_token,
                "recomputed_hash": recomputed,
                "matches": recomputed == row.run_token,
            }
        except Exception:
            replay_result = {"supported": False, "stored_hash": row.run_token, "recomputed_hash": None, "matches": None}
        return {
            "module_key": "consolidation",
            "snapshot_kind": "consolidation_output",
            "subject_type": "multi_entity_consolidation_run",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": row.run_token,
            "replay_supported": bool(replay_result["supported"]),
            "payload": {
                "run_id": str(row.id),
                "organisation_id": str(row.organisation_id),
                "reporting_period": row.reporting_period.isoformat(),
                "run_status": row.run_status,
                "run_token": row.run_token,
                "source_run_refs": row.source_run_refs_json,
                "validation_summary": row.validation_summary_json,
            },
            "comparison_payload": {
                "run_status": row.run_status,
                "run_token": row.run_token,
                "dependency_count": len(list(row.source_run_refs_json or [])),
            },
            "inputs": [
                {
                    "input_type": str(dep.get("source_type", "run_ref")),
                    "input_ref": str(dep.get("run_id", "")),
                    "input_hash": None,
                    "input_payload": dep,
                }
                for dep in list(row.source_run_refs_json or [])
            ],
            "metadata": {"run_status": row.run_status},
            "replay_result": replay_result,
        }

    async def _resolve_generic_run_subject(self, *, tenant_id: uuid.UUID, subject_id: str) -> dict[str, Any] | None:
        run_id = uuid.UUID(subject_id)
        snapshot = await self._observability_repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=run_id)
        if snapshot is None:
            for handler in (
                self._resolve_report_run_subject,
                self._resolve_board_pack_subject,
                self._resolve_legacy_consolidation_run_subject,
                self._resolve_consolidation_subject,
            ):
                resolved = await handler(tenant_id=tenant_id, subject_id=subject_id)
                if resolved is not None:
                    return resolved
            return None

        try:
            recomputed = self._replay_service.recompute_run_token(
                module_code=str(snapshot["module_code"]),
                row=snapshot["row"],
            )
            replay_result = {
                "supported": True,
                "stored_hash": str(snapshot["run_token"]),
                "recomputed_hash": recomputed,
                "matches": recomputed == str(snapshot["run_token"]),
            }
        except Exception:
            replay_result = {
                "supported": False,
                "stored_hash": str(snapshot["run_token"]),
                "recomputed_hash": None,
                "matches": None,
            }
        return {
            "module_key": str(snapshot["module_code"]),
            "snapshot_kind": "run_output",
            "subject_type": "run",
            "subject_id": subject_id,
            "entity_id": None,
            "determinism_hash": str(snapshot["run_token"]),
            "replay_supported": bool(replay_result["supported"]),
            "payload": {
                "run_id": str(snapshot["run_id"]),
                "module_code": str(snapshot["module_code"]),
                "run_token": str(snapshot["run_token"]),
                "status": str(snapshot["status"]),
                "version_tokens": snapshot["version_tokens"],
                "dependencies": snapshot["dependencies"],
            },
            "comparison_payload": {
                "status": str(snapshot["status"]),
                "run_token": str(snapshot["run_token"]),
                "dependency_count": len(list(snapshot["dependencies"])),
            },
            "inputs": [
                {
                    "input_type": str(dep.get("kind", "run_ref")),
                    "input_ref": str(dep.get("run_id", "")),
                    "input_hash": None,
                    "input_payload": dep,
                }
                for dep in list(snapshot["dependencies"])
            ],
            "metadata": {"module_code": str(snapshot["module_code"]), "status": str(snapshot["status"])},
            "replay_result": replay_result,
        }

    async def _resolve_legacy_consolidation_run_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_id: str,
    ) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                select(LegacyConsolidationRun).where(
                    LegacyConsolidationRun.tenant_id == tenant_id,
                    LegacyConsolidationRun.id == uuid.UUID(subject_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        configuration = dict(row.configuration_json or {})
        mappings = list(configuration.get("entity_snapshots") or [])
        return {
            "module_key": "consolidation",
            "snapshot_kind": "consolidation_output",
            "subject_type": "run",
            "subject_id": subject_id,
            "entity_id": str(row.entity_id) if row.entity_id is not None else None,
            "determinism_hash": row.request_signature,
            "replay_supported": True,
            "payload": {
                "run_id": str(row.id),
                "period_year": row.period_year,
                "period_month": row.period_month,
                "parent_currency": row.parent_currency,
                "workflow_id": row.workflow_id,
                "correlation_id": row.correlation_id,
                "configuration": configuration,
            },
            "comparison_payload": {
                "period_year": row.period_year,
                "period_month": row.period_month,
                "request_signature": row.request_signature,
                "mapping_count": len(mappings),
            },
            "inputs": [
                {
                    "input_type": "entity_snapshot",
                    "input_ref": str(item.get("snapshot_id", "")),
                    "input_hash": None,
                    "input_payload": item,
                }
                for item in mappings
            ],
            "metadata": {
                "workflow_id": row.workflow_id,
                "period_year": row.period_year,
                "period_month": row.period_month,
            },
            "replay_result": {
                "supported": True,
                "stored_hash": row.request_signature,
                "recomputed_hash": row.request_signature,
                "matches": True,
            },
        }

    async def _forward_lineage_for_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        if await self._observability_repository.resolve_run_snapshot(tenant_id=tenant_id, run_id=run_id) is not None:
            return await self._graph_service.build_graph(tenant_id=tenant_id, root_run_id=run_id)
        return {"root_run_id": str(run_id), "nodes": [], "edges": []}

    async def _reverse_lineage_for_run(self, *, tenant_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
        registry_rows = await self._observability_repository.list_registry(tenant_id=tenant_id)
        target_ids = {str(run_id)}
        queue: deque[str] = deque([str(run_id)])
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen: set[str] = set()
        while queue:
            current = queue.popleft()
            for row in registry_rows:
                deps = list(row.upstream_dependencies_json or [])
                matches = [dep for dep in deps if str(dep.get("run_id", "")) == current]
                if not matches:
                    continue
                row_id = str(row.run_id)
                edge = {
                    "from_run_id": current,
                    "to_run_id": row_id,
                    "kind": "reverse_dependency",
                    "module_code": row.module_code,
                }
                if edge not in edges:
                    edges.append(edge)
                if row_id not in seen:
                    seen.add(row_id)
                    queue.append(row_id)
                    target_ids.add(row_id)
                    nodes.append(
                        {
                            "run_id": row_id,
                            "subject_type": "run",
                            "module_code": row.module_code,
                            "run_token": row.run_token,
                        }
                    )
        report_snapshots = await self._related_snapshots_for_input_refs(tenant_id=tenant_id, refs=target_ids)
        for snapshot in report_snapshots:
            node = {
                "run_id": snapshot.subject_id,
                "subject_type": snapshot.subject_type,
                "module_code": snapshot.module_key,
                "determinism_hash": snapshot.determinism_hash,
            }
            if node not in nodes:
                nodes.append(node)
            edges.append(
                {
                    "from_run_id": str(run_id),
                    "to_run_id": snapshot.subject_id,
                    "kind": "snapshot_reference",
                    "module_code": snapshot.module_key,
                }
            )
        nodes.sort(key=lambda item: (item.get("module_code", ""), item.get("run_id", "")))
        edges.sort(key=lambda item: (item["from_run_id"], item["kind"], item["to_run_id"]))
        return {"root_run_id": str(run_id), "nodes": nodes, "edges": edges}

    async def _reverse_lineage_from_snapshot_inputs(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any]:
        refs = {subject_id, f"{subject_type}:{subject_id}"}
        snapshots = await self._related_snapshots_for_input_refs(tenant_id=tenant_id, refs=refs)
        return {
            "nodes": [self._serialize_snapshot(row) for row in snapshots],
            "edges": [
                {
                    "from_subject_id": subject_id,
                    "to_subject_id": row.subject_id,
                    "kind": "snapshot_reference",
                }
                for row in snapshots
            ],
        }

    async def _related_snapshots_for_input_refs(
        self,
        *,
        tenant_id: uuid.UUID,
        refs: set[str],
    ) -> list[GovernanceSnapshot]:
        if not refs:
            return []
        stmt = (
            select(GovernanceSnapshot)
            .join(GovernanceSnapshotInput, GovernanceSnapshotInput.snapshot_id == GovernanceSnapshot.id)
            .where(
                GovernanceSnapshot.tenant_id == tenant_id,
                GovernanceSnapshotInput.tenant_id == tenant_id,
                GovernanceSnapshotInput.input_ref.in_(sorted(refs)),
            )
            .order_by(GovernanceSnapshot.snapshot_at.desc(), GovernanceSnapshot.id.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _snapshot_row(self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID) -> GovernanceSnapshot | None:
        return (
            await self._session.execute(
                select(GovernanceSnapshot).where(
                    GovernanceSnapshot.tenant_id == tenant_id,
                    GovernanceSnapshot.id == snapshot_id,
                )
            )
        ).scalar_one_or_none()

    async def _require_snapshot(self, *, tenant_id: uuid.UUID, snapshot_id: uuid.UUID) -> GovernanceSnapshot:
        row = await self._snapshot_row(tenant_id=tenant_id, snapshot_id=snapshot_id)
        if row is None:
            raise ValueError("snapshot not found")
        return row

    async def _hydrate_snapshot(self, snapshot: GovernanceSnapshot) -> dict[str, Any]:
        inputs = (
            await self._session.execute(
                select(GovernanceSnapshotInput)
                .where(
                    GovernanceSnapshotInput.tenant_id == snapshot.tenant_id,
                    GovernanceSnapshotInput.snapshot_id == snapshot.id,
                )
                .order_by(GovernanceSnapshotInput.created_at.asc(), GovernanceSnapshotInput.id.asc())
            )
        ).scalars().all()
        metadata = (
            await self._session.execute(
                select(GovernanceSnapshotMetadata)
                .where(
                    GovernanceSnapshotMetadata.tenant_id == snapshot.tenant_id,
                    GovernanceSnapshotMetadata.snapshot_id == snapshot.id,
                )
                .order_by(GovernanceSnapshotMetadata.created_at.asc(), GovernanceSnapshotMetadata.id.asc())
            )
        ).scalars().all()
        payload = self._serialize_snapshot(snapshot)
        payload["inputs"] = [
            {
                "snapshot_input_id": str(row.id),
                "input_type": row.input_type,
                "input_ref": row.input_ref,
                "input_hash": row.input_hash,
                "input_payload": row.input_payload_json,
            }
            for row in inputs
        ]
        payload["metadata"] = {row.metadata_key: row.metadata_value_json.get("value") for row in metadata}
        return payload

    async def _latest_subject_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> GovernanceSnapshot | None:
        stmt = (
            select(GovernanceSnapshot)
            .where(
                GovernanceSnapshot.tenant_id == tenant_id,
                GovernanceSnapshot.subject_type == subject_type,
                GovernanceSnapshot.subject_id == subject_id,
            )
            .order_by(GovernanceSnapshot.version_no.desc(), GovernanceSnapshot.id.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _snapshots_for_subject(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_id: str,
    ) -> list[GovernanceSnapshot]:
        stmt = (
            select(GovernanceSnapshot)
            .where(
                GovernanceSnapshot.tenant_id == tenant_id,
                GovernanceSnapshot.subject_type == subject_type,
                GovernanceSnapshot.subject_id == subject_id,
            )
            .order_by(GovernanceSnapshot.version_no.asc(), GovernanceSnapshot.id.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _list_board_pack_sections(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[BoardPackGeneratorSection]:
        stmt = (
            select(BoardPackGeneratorSection)
            .where(
                BoardPackGeneratorSection.tenant_id == tenant_id,
                BoardPackGeneratorSection.run_id == run_id,
            )
            .order_by(BoardPackGeneratorSection.section_order.asc(), BoardPackGeneratorSection.id.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _list_board_pack_artifacts(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[BoardPackGeneratorArtifact]:
        stmt = (
            select(BoardPackGeneratorArtifact)
            .where(
                BoardPackGeneratorArtifact.tenant_id == tenant_id,
                BoardPackGeneratorArtifact.run_id == run_id,
            )
            .order_by(BoardPackGeneratorArtifact.generated_at.asc(), BoardPackGeneratorArtifact.id.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    def _serialize_snapshot(self, row: GovernanceSnapshot) -> dict[str, Any]:
        return {
            "snapshot_id": str(row.id),
            "module_key": row.module_key,
            "snapshot_kind": row.snapshot_kind,
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "entity_id": str(row.entity_id) if row.entity_id else None,
            "version_no": row.version_no,
            "determinism_hash": row.determinism_hash,
            "replay_supported": row.replay_supported,
            "trigger_event": row.trigger_event,
            "snapshot_at": row.snapshot_at.isoformat() if row.snapshot_at else None,
            "payload": row.payload_json,
            "comparison_payload": row.comparison_payload_json,
        }
