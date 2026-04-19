from __future__ import annotations


class ScheduledDeliveryError(Exception):
    pass


class DeliveryConfigError(ScheduledDeliveryError):
    def __init__(self, message: str):
        super().__init__(message)


class InvalidCronExpressionError(ScheduledDeliveryError):
    def __init__(self, expression: str):
        super().__init__(f"Invalid cron expression: '{expression}'")


__all__ = [
    "ScheduledDeliveryError",
    "DeliveryConfigError",
    "InvalidCronExpressionError",
]
