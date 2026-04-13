from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import sentry_sdk
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import apply_mutation_linkage, get_mutation_context
from financeops.modules.board_pack_generator.application.export_service import (
    BoardPackExportService,
)
from financeops.modules.board_pack_generator.domain.enums import (
    ExportFormat,
    PackRunStatus,
    PeriodType,
    SectionType,
)
from financeops.modules.board_pack_generator.domain.pack_assembler import PackAssembler
from financeops.modules.board_pack_generator.domain.pack_definition import (
    AssembledPack,
    PackDefinitionSchema,
    PackRunContext,
    RenderedSection,
    SectionConfig,
)
from financeops.modules.board_pack_generator.domain.section_renderer import get_renderer
from financeops.utils.display_scale import DisplayScale

if TYPE_CHECKING:
    from financeops.db.models.board_pack_generator import (
        BoardPackGeneratorDefinition,
        BoardPackGeneratorRun,
    )

log = logging.getLogger(__name__)


class InvalidRunStateError(Exception):
    pass


class BoardPackGenerationError(Exception):
    pass


class BoardPackGenerateService:
    _ALLOWED_TRANSITIONS: dict[PackRunStatus, set[PackRunStatus]] = {
        PackRunStatus.PENDING: {PackRunStatus.RUNNING},
        PackRunStatus.RUNNING: {PackRunStatus.COMPLETE, PackRunStatus.FAILED},
    }

    def __init__(
        self,
        *,
        assembler: PackAssembler | None = None,
        export_service: BoardPackExportService | None = None,
    ) -> None:
        self._assembler = assembler or PackAssembler()
        self._export_service = export_service or BoardPackExportService()

    async def generate(
        self,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> AssembledPack:
        running_run, context = await self.start_generation(
            db=db,
            run_id=run_id,
            tenant_id=tenant_id,
        )

        try:
            rendered_sections: list[RenderedSection] = []

            for section_config in sorted(
                context.definition.section_configs,
                key=lambda row: row.order,
            ):
                rendered_sections.append(
                    await self.generate_section(
                        db=db,
                        tenant_id=tenant_id,
                        run_id=running_run.id,
                        context=context,
                        section_config=section_config,
                    )
                )

            return await self.complete_generation(
                db=db,
                tenant_id=tenant_id,
                running_run=running_run,
                context=context,
                rendered_sections=rendered_sections,
            )
        except Exception as exc:
            await self.fail_generation(
                db=db,
                tenant_id=tenant_id,
                run_id=running_run.id,
                error_message=str(exc),
            )
            raise

    async def start_generation(
        self,
        *,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple["BoardPackGeneratorRun", PackRunContext]:
        run = await self._load_run(db=db, run_id=run_id, tenant_id=tenant_id)
        definition = await self._load_definition(
            db=db,
            definition_id=run.definition_id,
            tenant_id=tenant_id,
        )
        running_run = await self._transition_run_state(
            db=db,
            source_run=run,
            to_status=PackRunStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        await db.commit()
        return running_run, self._build_context(run=running_run, definition=definition)

    async def generate_section(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        context: PackRunContext,
        section_config: SectionConfig,
    ) -> RenderedSection:
        existing = await self._load_persisted_section(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            section_order=section_config.order,
        )
        if existing is not None:
            return existing

        source_data = await self._fetch_section_source_data(
            db=db,
            context=context,
            section_type=section_config.section_type,
        )
        renderer = get_renderer(section_config.section_type)
        rendered_section = renderer.render(
            context=context,
            section_config=section_config,
            source_data=source_data,
        )
        await self._persist_rendered_section(
            db=db,
            run_id=run_id,
            tenant_id=tenant_id,
            rendered_section=rendered_section,
        )
        return rendered_section

    async def complete_generation(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        running_run: "BoardPackGeneratorRun",
        context: PackRunContext,
        rendered_sections: list[RenderedSection],
    ) -> AssembledPack:
        assembled_pack = self._assembler.assemble(
            context=context,
            rendered_sections=rendered_sections,
        )

        generated_at = datetime.now(UTC)
        display_scale_raw = str(context.definition.config.get("display_scale", "LAKHS"))
        try:
            display_scale = DisplayScale(display_scale_raw)
        except ValueError:
            display_scale = DisplayScale.LAKHS
        try:
            pdf_bytes, pdf_filename = self._export_service.export_pdf(
                pack=assembled_pack,
                pack_name=context.definition.name,
                generated_at=generated_at,
                display_scale=display_scale,
            )
        except TypeError:
            pdf_bytes, pdf_filename = self._export_service.export_pdf(
                pack=assembled_pack,
                pack_name=context.definition.name,
                generated_at=generated_at,
            )
        try:
            xlsx_bytes, xlsx_filename = self._export_service.export_excel(
                pack=assembled_pack,
                pack_name=context.definition.name,
                generated_at=generated_at,
                display_scale=display_scale,
            )
        except TypeError:
            xlsx_bytes, xlsx_filename = self._export_service.export_excel(
                pack=assembled_pack,
                pack_name=context.definition.name,
                generated_at=generated_at,
            )

        await self._persist_artifact(
            db=db,
            run_id=running_run.id,
            tenant_id=tenant_id,
            export_format=ExportFormat.PDF,
            filename=pdf_filename,
            content=pdf_bytes,
            generated_at=generated_at,
        )
        await self._persist_artifact(
            db=db,
            run_id=running_run.id,
            tenant_id=tenant_id,
            export_format=ExportFormat.EXCEL,
            filename=xlsx_filename,
            content=xlsx_bytes,
            generated_at=generated_at,
        )

        await self._transition_run_state(
            db=db,
            source_run=running_run,
            to_status=PackRunStatus.COMPLETE,
            completed_at=datetime.now(UTC),
            chain_hash=assembled_pack.chain_hash,
        )
        mutation_context = get_mutation_context()
        from financeops.platform.services.control_plane.phase4_service import Phase4ControlPlaneService

        await Phase4ControlPlaneService(db).ensure_snapshot_for_subject(
            tenant_id=tenant_id,
            actor_user_id=(mutation_context.actor_user_id if mutation_context else None) or running_run.triggered_by,
            actor_role=(mutation_context.actor_role if mutation_context else None) or "system",
            subject_type="board_pack_run",
            subject_id=str(running_run.id),
            trigger_event="board_pack_generation_complete",
        )
        await db.commit()
        return assembled_pack

    async def fail_generation(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        error_message: str,
    ) -> None:
        await db.rollback()
        sentry_sdk.add_breadcrumb(
            category="board_pack_generator",
            message="board pack generation failed",
            level="error",
            data={
                "run_id": str(run_id),
                "tenant_id": str(tenant_id),
                "error": error_message,
            },
        )
        try:
            running_run = await self._load_run(db=db, run_id=run_id, tenant_id=tenant_id)
            await self._transition_run_state(
                db=db,
                source_run=running_run,
                to_status=PackRunStatus.FAILED,
                completed_at=datetime.now(UTC),
                error_message=error_message[:2000],
            )
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception(
                "Failed to append FAILED run status row",
                extra={"run_id": str(run_id), "tenant_id": str(tenant_id)},
            )

    async def load_rendered_sections(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> list[RenderedSection]:
        from financeops.db.models.board_pack_generator import BoardPackGeneratorSection

        rows = (
            await db.execute(
                select(BoardPackGeneratorSection)
                .where(
                    BoardPackGeneratorSection.tenant_id == tenant_id,
                    BoardPackGeneratorSection.run_id == run_id,
                )
                .order_by(
                    BoardPackGeneratorSection.section_order.asc(),
                    BoardPackGeneratorSection.id.asc(),
                )
            )
        ).scalars().all()
        rendered: list[RenderedSection] = []
        for row in rows:
            payload = dict(row.data_snapshot or {})
            rendered.append(
                RenderedSection(
                    section_type=SectionType(str(row.section_type)),
                    section_order=int(row.section_order),
                    title=str(payload.get("title") or str(row.section_type).replace("_", " ").title()),
                    data_snapshot=payload,
                    section_hash=str(row.section_hash),
                )
            )
        return rendered

    async def _load_run(
        self,
        *,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> "BoardPackGeneratorRun":
        from financeops.db.models.board_pack_generator import BoardPackGeneratorRun

        row = (
            await db.execute(
                select(BoardPackGeneratorRun).where(
                    BoardPackGeneratorRun.id == run_id,
                    BoardPackGeneratorRun.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise BoardPackGenerationError("Board pack run not found")
        return row

    async def _load_definition(
        self,
        *,
        db: AsyncSession,
        definition_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> "BoardPackGeneratorDefinition":
        from financeops.db.models.board_pack_generator import BoardPackGeneratorDefinition

        row = (
            await db.execute(
                select(BoardPackGeneratorDefinition).where(
                    BoardPackGeneratorDefinition.id == definition_id,
                    BoardPackGeneratorDefinition.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise BoardPackGenerationError("Board pack definition not found")
        return row

    def _build_context(
        self,
        *,
        run: "BoardPackGeneratorRun",
        definition: "BoardPackGeneratorDefinition",
    ) -> PackRunContext:
        section_configs = self._build_section_configs(definition)
        entity_ids_raw = list(definition.entity_ids or [])
        entity_ids = [uuid.UUID(str(value)) for value in entity_ids_raw]
        period_type = PeriodType(str(definition.period_type))
        definition_schema = PackDefinitionSchema(
            name=definition.name,
            description=definition.description,
            section_configs=section_configs,
            entity_ids=entity_ids,
            period_type=period_type,
            config=dict(definition.config or {}),
        )
        return PackRunContext(
            run_id=run.id,
            tenant_id=run.tenant_id,
            definition=definition_schema,
            period_start=run.period_start,
            period_end=run.period_end,
            triggered_by=run.triggered_by,
        )

    def _build_section_configs(
        self,
        definition: "BoardPackGeneratorDefinition",
    ) -> list[SectionConfig]:
        cfg = dict(definition.config or {})
        configured = cfg.get("section_configs")
        if isinstance(configured, list) and configured:
            result: list[SectionConfig] = []
            for idx, item in enumerate(configured, start=1):
                if not isinstance(item, dict):
                    continue
                section_type = SectionType(str(item.get("section_type")))
                order = int(item.get("order", idx))
                title = item.get("title")
                section_cfg = item.get("config") if isinstance(item.get("config"), dict) else {}
                result.append(
                    SectionConfig(
                        section_type=section_type,
                        order=order,
                        title=title,
                        config=section_cfg,
                    )
                )
            if result:
                return result

        result: list[SectionConfig] = []
        for index, section_type_raw in enumerate(list(definition.section_types or []), start=1):
            result.append(
                SectionConfig(
                    section_type=SectionType(str(section_type_raw)),
                    order=index,
                    title=None,
                    config={},
                )
            )
        if not result:
            raise BoardPackGenerationError("Board pack definition has no section configuration")
        return result

    async def _transition_run_state(
        self,
        *,
        db: AsyncSession,
        source_run: "BoardPackGeneratorRun",
        to_status: PackRunStatus,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
        chain_hash: str | None = None,
    ) -> "BoardPackGeneratorRun":
        from financeops.db.models.board_pack_generator import BoardPackGeneratorRun

        from_status = PackRunStatus(str(source_run.status))
        allowed = self._ALLOWED_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidRunStateError(
                f"Invalid run state transition: {from_status.value} -> {to_status.value}"
            )

        metadata = dict(source_run.run_metadata or {})
        origin_run_id = metadata.get("origin_run_id", str(source_run.id))
        metadata["origin_run_id"] = origin_run_id
        metadata["previous_run_id"] = str(source_run.id)
        metadata["state_transition"] = f"{from_status.value}->{to_status.value}"
        metadata["transitioned_at"] = datetime.now(UTC).isoformat()

        next_row = BoardPackGeneratorRun(
            tenant_id=source_run.tenant_id,
            definition_id=source_run.definition_id,
            period_start=source_run.period_start,
            period_end=source_run.period_end,
            status=to_status.value,
            triggered_by=source_run.triggered_by,
            started_at=started_at if to_status == PackRunStatus.RUNNING else source_run.started_at,
            completed_at=completed_at if to_status in {PackRunStatus.COMPLETE, PackRunStatus.FAILED} else None,
            error_message=error_message if to_status == PackRunStatus.FAILED else None,
            chain_hash=chain_hash if to_status == PackRunStatus.COMPLETE else None,
            run_metadata=metadata,
        )
        if get_mutation_context() is not None:
            apply_mutation_linkage(next_row)
        db.add(next_row)
        await db.flush()
        return next_row

    async def _persist_rendered_section(
        self,
        *,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        rendered_section: RenderedSection,
    ) -> None:
        from financeops.db.models.board_pack_generator import BoardPackGeneratorSection

        row = BoardPackGeneratorSection(
            run_id=run_id,
            tenant_id=tenant_id,
            section_type=rendered_section.section_type.value,
            section_order=rendered_section.section_order,
            data_snapshot=rendered_section.data_snapshot,
            section_hash=rendered_section.section_hash,
        )
        if get_mutation_context() is not None:
            apply_mutation_linkage(row)
        db.add(row)
        await db.flush()

    async def _load_persisted_section(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        section_order: int,
    ) -> RenderedSection | None:
        from financeops.db.models.board_pack_generator import BoardPackGeneratorSection

        row = (
            await db.execute(
                select(BoardPackGeneratorSection).where(
                    BoardPackGeneratorSection.tenant_id == tenant_id,
                    BoardPackGeneratorSection.run_id == run_id,
                    BoardPackGeneratorSection.section_order == section_order,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        payload = dict(row.data_snapshot or {})
        return RenderedSection(
            section_type=SectionType(str(row.section_type)),
            section_order=int(row.section_order),
            title=str(payload.get("title") or str(row.section_type).replace("_", " ").title()),
            data_snapshot=payload,
            section_hash=str(row.section_hash),
        )

    async def _persist_artifact(
        self,
        *,
        db: AsyncSession,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        export_format: ExportFormat,
        filename: str,
        content: bytes,
        generated_at: datetime,
    ) -> None:
        from financeops.db.models.board_pack_generator import BoardPackGeneratorArtifact

        storage_path = f"artifacts/board_packs/{tenant_id}/{run_id}/{filename}"
        artifact = BoardPackGeneratorArtifact(
            run_id=run_id,
            tenant_id=tenant_id,
            format=export_format.value,
            storage_path=storage_path,
            file_size_bytes=len(content),
            generated_at=generated_at,
            checksum=RenderedSection.compute_hash({"filename": filename, "content_length": len(content)}),
        )
        if get_mutation_context() is not None:
            apply_mutation_linkage(artifact)
        db.add(artifact)
        await db.flush()

    async def _fetch_section_source_data(
        self,
        *,
        db: AsyncSession,
        context: PackRunContext,
        section_type: SectionType,
    ) -> dict[str, Any]:
        fetchers: dict[SectionType, Any] = {
            SectionType.PROFIT_AND_LOSS: self._fetch_profit_and_loss,
            SectionType.BALANCE_SHEET: self._fetch_balance_sheet,
            SectionType.CASH_FLOW: self._fetch_cash_flow,
            SectionType.KPI_SUMMARY: self._fetch_kpi_summary,
            SectionType.RATIO_ANALYSIS: self._fetch_ratio_analysis,
            SectionType.NARRATIVE: self._fetch_narrative,
            SectionType.FX_SUMMARY: self._fetch_fx_summary,
            SectionType.ENTITY_CONSOLIDATION: self._fetch_entity_consolidation,
        }
        fetcher = fetchers[section_type]
        return await fetcher(db=db, context=context)

    async def _fetch_profit_and_loss(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM multi_entity_consolidation_runs
                WHERE tenant_id = :tenant_id
                  AND run_status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="multi_entity_consolidation_pnl")

        rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, currency_code, aggregated_value, materiality_flag
                FROM multi_entity_consolidation_metric_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        pnl_rows = [
            row
            for row in rows
            if any(
                token in str(row.get("metric_code", "")).lower()
                for token in ("revenue", "income", "expense", "profit", "ebitda", "cogs", "gross", "net")
            )
        ]
        return {
            "status": "ok",
            "source": "multi_entity_consolidation_metric_results",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "rows": pnl_rows or rows,
        }

    async def _fetch_balance_sheet(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM multi_entity_consolidation_runs
                WHERE tenant_id = :tenant_id
                  AND run_status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="multi_entity_consolidation_bs")

        rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, currency_code, aggregated_value, materiality_flag
                FROM multi_entity_consolidation_metric_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        bs_rows = [
            row
            for row in rows
            if any(
                token in str(row.get("metric_code", "")).lower()
                for token in ("asset", "liability", "equity", "cash", "receivable", "payable", "inventory", "debt")
            )
        ]
        return {
            "status": "ok",
            "source": "multi_entity_consolidation_metric_results",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "rows": bs_rows or rows,
        }

    async def _fetch_cash_flow(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM cash_flow_runs
                WHERE tenant_id = :tenant_id
                  AND run_status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="cash_flow_line_results")

        rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, line_code, line_name, section_code, computed_value, currency_code
                FROM cash_flow_line_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        return {
            "status": "ok",
            "source": "cash_flow_line_results",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "rows": rows,
        }

    async def _fetch_kpi_summary(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM metric_runs
                WHERE tenant_id = :tenant_id
                  AND status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="metric_results_kpi")

        rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, metric_value, favorable_status, materiality_flag
                FROM metric_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        return {
            "status": "ok",
            "source": "metric_results",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "rows": rows,
        }

    async def _fetch_ratio_analysis(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM metric_runs
                WHERE tenant_id = :tenant_id
                  AND status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="variance_results")

        rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, comparison_type, variance_abs, variance_pct, variance_bps
                FROM variance_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        return {
            "status": "ok",
            "source": "variance_results",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "rows": rows,
        }

    async def _fetch_narrative(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        result_row = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, run_id, reporting_period, executive_summary_text, overall_health_classification
                FROM board_pack_results
                WHERE tenant_id = :tenant_id
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if result_row is None:
            return self._no_data(context=context, source="board_pack_narrative")

        sections = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT section_order, section_code, section_title, section_summary_text, section_payload_json
                FROM board_pack_section_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY section_order ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": result_row["run_id"]},
        )
        blocks = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT block_order, narrative_template_code, narrative_text, narrative_payload_json
                FROM board_pack_narrative_blocks
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY block_order ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": result_row["run_id"]},
        )
        return {
            "status": "ok",
            "source": "board_pack_narrative",
            "board_pack_result_id": str(result_row["id"]),
            "run_id": str(result_row["run_id"]),
            "reporting_period": str(result_row["reporting_period"]),
            "executive_summary_text": result_row["executive_summary_text"],
            "overall_health_classification": result_row["overall_health_classification"],
            "sections": sections,
            "blocks": blocks,
        }

    async def _fetch_fx_summary(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period, reporting_currency_code
                FROM fx_translation_runs
                WHERE tenant_id = :tenant_id
                  AND run_status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="fx_translation_reporting")

        metric_rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, reporting_currency_code, translated_value, applied_rate_type, applied_rate_value
                FROM fx_translated_metric_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        variance_rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, metric_code, comparison_type, translated_variance_value, variance_pct
                FROM fx_translated_variance_results
                WHERE tenant_id = :tenant_id
                  AND run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        return {
            "status": "ok",
            "source": "fx_translation_reporting",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "reporting_currency_code": run["reporting_currency_code"],
            "metric_rows": metric_rows,
            "variance_rows": variance_rows,
        }

    async def _fetch_entity_consolidation(
        self,
        db: AsyncSession,
        context: PackRunContext,
    ) -> dict[str, Any]:
        run = await self._latest_run_row(
            db=db,
            sql=text(
                """
                SELECT id, reporting_period
                FROM ownership_consolidation_runs
                WHERE tenant_id = :tenant_id
                  AND run_status = 'completed'
                  AND reporting_period BETWEEN :period_start AND :period_end
                ORDER BY reporting_period DESC, created_at DESC
                LIMIT 1
                """
            ),
            context=context,
        )
        if run is None:
            return self._no_data(context=context, source="ownership_consolidation")

        metric_rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, scope_code, metric_code, attributed_value, ownership_weight_applied, reporting_currency_code_nullable
                FROM ownership_consolidation_metric_results
                WHERE tenant_id = :tenant_id
                  AND ownership_consolidation_run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        variance_rows = await self._query_rows(
            db=db,
            sql=text(
                """
                SELECT line_no, scope_code, metric_code, variance_code, attributed_variance_abs, attributed_variance_pct
                FROM ownership_consolidation_variance_results
                WHERE tenant_id = :tenant_id
                  AND ownership_consolidation_run_id = :run_id
                ORDER BY line_no ASC
                """
            ),
            params={"tenant_id": context.tenant_id, "run_id": run["id"]},
        )
        return {
            "status": "ok",
            "source": "ownership_consolidation",
            "run_id": str(run["id"]),
            "reporting_period": str(run["reporting_period"]),
            "metric_rows": metric_rows,
            "variance_rows": variance_rows,
        }

    async def _latest_run_row(
        self,
        *,
        db: AsyncSession,
        sql: Any,
        context: PackRunContext,
    ) -> dict[str, Any] | None:
        result = await db.execute(
            sql,
            {
                "tenant_id": str(context.tenant_id),
                "period_start": context.period_start,
                "period_end": context.period_end,
            },
        )
        row = result.mappings().first()
        return dict(row) if row is not None else None

    async def _query_rows(
        self,
        *,
        db: AsyncSession,
        sql: Any,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = await db.execute(sql, params)
        return [dict(row) for row in result.mappings().all()]

    def _no_data(self, *, context: PackRunContext, source: str) -> dict[str, Any]:
        return {
            "status": "no_data",
            "source": source,
            "period_start": context.period_start,
            "period_end": context.period_end,
        }
