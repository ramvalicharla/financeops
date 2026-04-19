from __future__ import annotations


class ErpSyncError(Exception):
    pass


class DuplicateGLEntryError(ErpSyncError):
    def __init__(self, external_ref: str):
        self.external_ref = external_ref
        super().__init__(f"GL entry already posted for ref: {external_ref}")


__all__ = ["ErpSyncError", "DuplicateGLEntryError"]
