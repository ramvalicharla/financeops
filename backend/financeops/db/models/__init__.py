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
    "ChecklistTemplate",
    "ChecklistTemplateTask",
    "ChecklistRun",
    "ChecklistRunTask",
    "WCSnapshot",
    "ARLineItem",
    "APLineItem",
    "ExpensePolicy",
    "ExpenseClaim",
    "ExpenseApproval",
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
    "ChecklistTemplate": ("financeops.modules.closing_checklist.models", "ChecklistTemplate"),
    "ChecklistTemplateTask": ("financeops.modules.closing_checklist.models", "ChecklistTemplateTask"),
    "ChecklistRun": ("financeops.modules.closing_checklist.models", "ChecklistRun"),
    "ChecklistRunTask": ("financeops.modules.closing_checklist.models", "ChecklistRunTask"),
    "WCSnapshot": ("financeops.modules.working_capital.models", "WCSnapshot"),
    "ARLineItem": ("financeops.modules.working_capital.models", "ARLineItem"),
    "APLineItem": ("financeops.modules.working_capital.models", "APLineItem"),
    "ExpensePolicy": ("financeops.modules.expense_management.models", "ExpensePolicy"),
    "ExpenseClaim": ("financeops.modules.expense_management.models", "ExpenseClaim"),
    "ExpenseApproval": ("financeops.modules.expense_management.models", "ExpenseApproval"),
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
