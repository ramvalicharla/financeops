from __future__ import annotations

from financeops.modules.board_pack_generator.domain.pack_definition import (
    AssembledPack,
    PackRunContext,
    RenderedSection,
)


class PackAssembler:
    def assemble(
        self,
        context: PackRunContext,
        rendered_sections: list[RenderedSection],
    ) -> AssembledPack:
        ordered_sections = sorted(rendered_sections, key=lambda row: row.section_order)
        orders = [section.section_order for section in ordered_sections]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate section_order values are not allowed")

        chain_hash = AssembledPack.compute_chain_hash(ordered_sections)
        return AssembledPack(
            run_id=context.run_id,
            tenant_id=context.tenant_id,
            period_start=context.period_start,
            period_end=context.period_end,
            sections=ordered_sections,
            chain_hash=chain_hash,
        )


__all__ = ["PackAssembler"]

