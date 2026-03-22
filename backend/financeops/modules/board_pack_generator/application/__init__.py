from __future__ import annotations

from typing import TYPE_CHECKING, Any

from financeops.modules.board_pack_generator.application.export_service import (
    BoardPackExportService,
)
from financeops.modules.board_pack_generator.application.generate_service import (
    BoardPackGenerateService,
)

if TYPE_CHECKING:
    from financeops.modules.board_pack_generator.tasks import generate_board_pack_task as generate_board_pack_task

__all__ = [
    "BoardPackExportService",
    "BoardPackGenerateService",
    "generate_board_pack_task",
]


def __getattr__(name: str) -> Any:
    if name == "generate_board_pack_task":
        from financeops.modules.board_pack_generator.tasks import (
            generate_board_pack_task as _generate_board_pack_task,
        )

        return _generate_board_pack_task
    raise AttributeError(name)
