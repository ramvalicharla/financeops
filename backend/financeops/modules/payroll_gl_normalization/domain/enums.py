from __future__ import annotations

from enum import Enum


class SourceFamily(str, Enum):
    PAYROLL = "payroll"
    GL = "gl"
    ERP_GL_API = "erp_gl_api"
    PAYROLL_PROVIDER_EXPORT = "payroll_provider_export"


class RunType(str, Enum):
    PAYROLL_NORMALIZATION = "payroll_normalization"
    GL_NORMALIZATION = "gl_normalization"


class RunStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    FINALIZED = "finalized"
    FAILED = "failed"


class LineStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class ExceptionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
