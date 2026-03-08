from __future__ import annotations

from financeops.modules.anomaly_pattern_engine.domain.enums import (
    PersistenceClassification,
    SeverityLevel,
)


class PersistenceService:
    def classify(
        self,
        *,
        prior_severity: str | None,
        current_severity: SeverityLevel,
        recurrence_count: int,
        recurrence_threshold: int,
    ) -> PersistenceClassification:
        if prior_severity is None:
            return PersistenceClassification.FIRST_DETECTED
        if prior_severity == SeverityLevel.INFO.value and current_severity != SeverityLevel.INFO:
            return PersistenceClassification.REOPENED
        if current_severity == SeverityLevel.INFO and prior_severity != SeverityLevel.INFO.value:
            return PersistenceClassification.RESOLVED
        if recurrence_count >= recurrence_threshold:
            return PersistenceClassification.SUSTAINED
        if prior_severity == current_severity.value:
            return PersistenceClassification.RECURRING
        if self._rank(current_severity.value) > self._rank(prior_severity):
            return PersistenceClassification.ESCALATING
        return PersistenceClassification.RECURRING

    def _rank(self, value: str) -> int:
        order = {
            SeverityLevel.INFO.value: 0,
            SeverityLevel.LOW.value: 1,
            SeverityLevel.MEDIUM.value: 2,
            SeverityLevel.HIGH.value: 3,
            SeverityLevel.CRITICAL.value: 4,
        }
        return order.get(value, 0)
