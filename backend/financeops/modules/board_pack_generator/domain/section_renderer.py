from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from financeops.modules.board_pack_generator.domain.enums import SectionType
from financeops.modules.board_pack_generator.domain.pack_definition import (
    PackRunContext,
    RenderedSection,
    SectionConfig,
)

_DEFAULT_SECTION_TITLES: dict[SectionType, str] = {
    SectionType.PROFIT_AND_LOSS: "Profit and Loss",
    SectionType.BALANCE_SHEET: "Balance Sheet",
    SectionType.CASH_FLOW: "Cash Flow",
    SectionType.KPI_SUMMARY: "KPI Summary",
    SectionType.RATIO_ANALYSIS: "Ratio Analysis",
    SectionType.NARRATIVE: "Narrative",
    SectionType.FX_SUMMARY: "FX Summary",
    SectionType.ENTITY_CONSOLIDATION: "Entity Consolidation",
}


class SectionRendererBase(ABC):
    section_type: SectionType

    @abstractmethod
    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        raise NotImplementedError

    def _decimal_safe(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._decimal_safe(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._decimal_safe(item) for item in value]
        if isinstance(value, tuple):
            return [self._decimal_safe(item) for item in value]
        return value

    def _build_section(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        payload = self._decimal_safe(source_data)
        snapshot = {
            "section_type": section_config.section_type.value,
            "title": section_config.title or _DEFAULT_SECTION_TITLES[section_config.section_type],
            "period_start": context.period_start.isoformat(),
            "period_end": context.period_end.isoformat(),
            "entity_ids": [str(entity_id) for entity_id in context.definition.entity_ids],
            "config": self._decimal_safe(section_config.config),
            "payload": payload,
        }
        return RenderedSection(
            section_type=self.section_type,
            section_order=section_config.order,
            title=section_config.title or _DEFAULT_SECTION_TITLES[section_config.section_type],
            data_snapshot=snapshot,
            section_hash=RenderedSection.compute_hash(snapshot),
        )


class ProfitAndLossRenderer(SectionRendererBase):
    section_type = SectionType.PROFIT_AND_LOSS

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class BalanceSheetRenderer(SectionRendererBase):
    section_type = SectionType.BALANCE_SHEET

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class CashFlowRenderer(SectionRendererBase):
    section_type = SectionType.CASH_FLOW

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class KpiSummaryRenderer(SectionRendererBase):
    section_type = SectionType.KPI_SUMMARY

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class RatioAnalysisRenderer(SectionRendererBase):
    section_type = SectionType.RATIO_ANALYSIS

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class NarrativeRenderer(SectionRendererBase):
    section_type = SectionType.NARRATIVE

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class FxSummaryRenderer(SectionRendererBase):
    section_type = SectionType.FX_SUMMARY

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


class EntityConsolidationRenderer(SectionRendererBase):
    section_type = SectionType.ENTITY_CONSOLIDATION

    def render(
        self,
        context: PackRunContext,
        section_config: SectionConfig,
        source_data: dict[str, Any],
    ) -> RenderedSection:
        return self._build_section(context, section_config, source_data)


RENDERER_REGISTRY: dict[SectionType, SectionRendererBase] = {
    SectionType.PROFIT_AND_LOSS: ProfitAndLossRenderer(),
    SectionType.BALANCE_SHEET: BalanceSheetRenderer(),
    SectionType.CASH_FLOW: CashFlowRenderer(),
    SectionType.KPI_SUMMARY: KpiSummaryRenderer(),
    SectionType.RATIO_ANALYSIS: RatioAnalysisRenderer(),
    SectionType.NARRATIVE: NarrativeRenderer(),
    SectionType.FX_SUMMARY: FxSummaryRenderer(),
    SectionType.ENTITY_CONSOLIDATION: EntityConsolidationRenderer(),
}


def get_renderer(section_type: SectionType) -> SectionRendererBase:
    if section_type not in RENDERER_REGISTRY:
        raise ValueError(f"No renderer registered for {section_type}")
    return RENDERER_REGISTRY[section_type]


__all__ = [
    "BalanceSheetRenderer",
    "CashFlowRenderer",
    "EntityConsolidationRenderer",
    "FxSummaryRenderer",
    "KpiSummaryRenderer",
    "NarrativeRenderer",
    "ProfitAndLossRenderer",
    "RENDERER_REGISTRY",
    "RatioAnalysisRenderer",
    "SectionRendererBase",
    "get_renderer",
]
