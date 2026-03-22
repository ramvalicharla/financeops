"""Board pack generator module."""

from __future__ import annotations

import logging

from financeops.modules.board_pack_generator.application.export_service import (
    get_weasyprint_mode,
)

log = logging.getLogger(__name__)
log.info("WeasyPrint mode: %s", get_weasyprint_mode())
