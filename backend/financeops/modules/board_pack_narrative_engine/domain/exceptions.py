from __future__ import annotations


class NarrativeEngineError(Exception):
    pass


class NarrativeSummaryGenerationError(NarrativeEngineError):
    def __init__(self, reason: str):
        super().__init__(f"Failed to generate executive summary: {reason}")
