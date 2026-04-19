from __future__ import annotations


class AICFOError(Exception):
    pass


class AIProviderUnavailableError(AICFOError):
    def __init__(self, message: str):
        super().__init__(message)


class AIResponseValidationError(AICFOError):
    def __init__(self, message: str):
        super().__init__(message)
