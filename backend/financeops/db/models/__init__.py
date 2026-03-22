from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ReportDefinition",
    "ReportRun",
    "ReportResult",
    "BoardPackGeneratorRun",
    "BoardPackGeneratorDefinition",
    "BoardPackGeneratorSection",
    "BoardPackGeneratorArtifact",
    "DeliverySchedule",
    "DeliveryLog",
    "PipelineRun",
    "PipelineStepLog",
    "OnboardingState",
    "SecretRotationLog",
    "UserPiiKey",
    "ErasureLog",
    "AICostEvent",
    "TenantTokenBudget",
]

_MODEL_IMPORTS: dict[str, tuple[str, str]] = {
    "ReportDefinition": ("financeops.db.models.custom_report_builder", "ReportDefinition"),
    "ReportRun": ("financeops.db.models.custom_report_builder", "ReportRun"),
    "ReportResult": ("financeops.db.models.custom_report_builder", "ReportResult"),
    "BoardPackGeneratorRun": (
        "financeops.db.models.board_pack_generator",
        "BoardPackGeneratorRun",
    ),
    "BoardPackGeneratorDefinition": (
        "financeops.db.models.board_pack_generator",
        "BoardPackGeneratorDefinition",
    ),
    "BoardPackGeneratorSection": (
        "financeops.db.models.board_pack_generator",
        "BoardPackGeneratorSection",
    ),
    "BoardPackGeneratorArtifact": (
        "financeops.db.models.board_pack_generator",
        "BoardPackGeneratorArtifact",
    ),
    "DeliverySchedule": ("financeops.db.models.scheduled_delivery", "DeliverySchedule"),
    "DeliveryLog": ("financeops.db.models.scheduled_delivery", "DeliveryLog"),
    "PipelineRun": ("financeops.modules.auto_trigger.models", "PipelineRun"),
    "PipelineStepLog": ("financeops.modules.auto_trigger.models", "PipelineStepLog"),
    "OnboardingState": ("financeops.modules.template_onboarding.models", "OnboardingState"),
    "SecretRotationLog": ("financeops.modules.secret_rotation.models", "SecretRotationLog"),
    "UserPiiKey": ("financeops.modules.compliance.models", "UserPiiKey"),
    "ErasureLog": ("financeops.modules.compliance.models", "ErasureLog"),
    "AICostEvent": ("financeops.db.models.ai_cost", "AICostEvent"),
    "TenantTokenBudget": ("financeops.db.models.ai_cost", "TenantTokenBudget"),
}


def __getattr__(name: str) -> Any:
    target = _MODEL_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
