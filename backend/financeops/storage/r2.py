"""
R2 Storage Client.

SECURITY: delete_file() must only be called from
admin-authorized routes or internal cleanup tasks.
Never expose to tenant-level API without explicit
role enforcement at the route layer.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from financeops.config import settings

log = logging.getLogger(__name__)
_WORM_ENGINE: Engine | None = None
_WORM_SESSION_FACTORY: sessionmaker[Session] | None = None


def _sync_database_url() -> str:
    url = make_url(str(settings.DATABASE_URL))
    if url.drivername == "postgresql+asyncpg":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername == "sqlite+aiosqlite":
        url = url.set(drivername="sqlite+pysqlite")
    elif "+async" in url.drivername:
        url = url.set(drivername=url.drivername.replace("+async", "+"))
    return str(url)


def _get_worm_session_factory() -> sessionmaker[Session]:
    global _WORM_ENGINE, _WORM_SESSION_FACTORY
    if _WORM_SESSION_FACTORY is None:
        _WORM_ENGINE = create_engine(
            _sync_database_url(),
            pool_pre_ping=True,
        )
        _WORM_SESSION_FACTORY = sessionmaker(
            bind=_WORM_ENGINE,
            autoflush=False,
            expire_on_commit=False,
        )
    return _WORM_SESSION_FACTORY


def _find_worm_locked_attachment(key: str) -> tuple[str, str | None] | None:
    from financeops.db.models.accounting_vendor import AccountingAttachment

    factory = _get_worm_session_factory()
    with factory() as db:
        row = (
            db.execute(
                select(AccountingAttachment.id, AccountingAttachment.jv_id).where(
                    AccountingAttachment.r2_key == key,
                    AccountingAttachment.worm_locked.is_(True),
                )
            )
            .first()
        )
    if row is None:
        return None
    attachment_id, jv_id = row
    return str(attachment_id), str(jv_id) if jv_id is not None else None


class R2Storage:
    """
    Cloudflare R2 storage client using boto3 S3-compatible API.
    All operations are synchronous boto3 calls wrapped in async wrappers
    for use in a thread pool — direct async boto3 is not available.
    """

    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL or None,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY or None,
            region_name="auto",
        )
        self._bucket = settings.R2_BUCKET_NAME

    def _build_key(
        self,
        tenant_id: str,
        module: str,
        filename: str,
    ) -> str:
        """Build storage key: {tenant_id}/{module}/{uuid}/{filename}"""
        file_uuid = str(uuid.uuid4())
        return f"{tenant_id}/{module}/{file_uuid}/{filename}"

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str,
        tenant_id: str,
        uploaded_by: str | None = None,
    ) -> str:
        """Upload bytes to R2. Returns the full object key (URL constructed by caller)."""
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        metadata: dict[str, str] = {
            "tenant_id": tenant_id,
            "sha256_hash": sha256,
        }
        if uploaded_by:
            metadata["uploaded_by"] = uploaded_by

        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
            Metadata=metadata,
        )
        log.info("R2 upload: key=%s size=%d sha256=%s", key, len(file_bytes), sha256[:12])
        return key

    def download_file(self, key: str) -> bytes:
        """Download object from R2 and return raw bytes."""
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def delete_file(self, key: str, worm_check: bool | None = None) -> bool:
        """Delete object from R2. Returns True on success."""
        if worm_check is not False:
            try:
                locked = _find_worm_locked_attachment(key)
                if locked is not None:
                    attachment_id, jv_id = locked
                    log.error(
                        "r2_delete_blocked_worm",
                        extra={
                            "key": key,
                            "attachment_id": attachment_id,
                            "jv_id": jv_id,
                            "audit": True,
                        },
                    )
                    return False
            except Exception as worm_exc:
                # Fail-safe: if lock verification fails, block deletion.
                log.error(
                    "r2_worm_check_failed_blocking_delete",
                    extra={"key": key, "error": str(worm_exc)},
                )
                return False
        try:
            log.warning(
                "r2_delete_called",
                extra={
                    "key": key,
                    "audit": True,
                    "worm_note": "verify no approved JV link",
                },
            )
            self._client.delete_object(Bucket=self._bucket, Key=key)
            log.info("R2 delete: key=%s", key)
            return True
        except ClientError as exc:
            log.error("R2 delete failed: key=%s error=%s", key, exc)
            return False

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited presigned URL for direct client download."""
        url = self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    def file_exists(self, key: str) -> bool:
        """Return True if the object exists in R2."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise
