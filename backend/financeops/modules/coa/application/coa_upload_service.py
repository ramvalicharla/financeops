from __future__ import annotations

import csv
import io
import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from financeops.modules.coa.models import (
    CoaAccountGroup,
    CoaAccountSubgroup,
    CoaIndustryTemplate,
    CoaLedgerAccount,
    CoaSourceType,
    CoaUploadBatch,
    CoaUploadMode,
    CoaUploadStagingRow,
    CoaUploadStatus,
)

_REQUIRED_COLUMNS = (
    "group_code",
    "group_name",
    "subgroup_code",
    "subgroup_name",
    "ledger_code",
    "ledger_name",
    "ledger_type",
    "is_control_account",
)
_ALLOWED_LEDGER_TYPES = {"ASSET", "LIABILITY", "INCOME", "EXPENSE"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_ACCOUNT_ALIASES = ("account", "particulars", "ledger", "name")
_DEBIT_ALIASES = ("debit", "dr")
_CREDIT_ALIASES = ("credit", "cr")
log = logging.getLogger(__name__)


class CoaUploadService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _normalise_header(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _read_dataframe(*, file_name: str, file_bytes: bytes) -> pd.DataFrame:
        lower_name = file_name.lower()
        if lower_name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
        if lower_name.endswith(".xlsx"):
            return pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        raise ValidationError("Only .csv or .xlsx files are supported")

    @classmethod
    def _match_alias(cls, columns: list[str], aliases: tuple[str, ...]) -> str | None:
        alias_set = {alias.lower() for alias in aliases}
        for column in columns:
            if cls._normalise_header(column) in alias_set:
                return column
        return None

    @staticmethod
    def _clean_numeric_series(series: pd.Series) -> pd.Series:
        cleaned = (
            series.fillna("")
            .astype(str)
            .str.strip()
            .str.replace(",", "", regex=False)
            .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
        )
        numeric = pd.to_numeric(cleaned.replace("", pd.NA), errors="coerce")
        return numeric

    def parse_normalized_dataframe(self, *, file_name: str, file_bytes: bytes) -> pd.DataFrame:
        if len(file_bytes) > _MAX_UPLOAD_BYTES:
            raise ValidationError("File size exceeds 5MB limit")

        dataframe = self._read_dataframe(file_name=file_name, file_bytes=file_bytes).copy()
        dataframe.columns = [str(column or "").strip() for column in dataframe.columns]
        original_columns = list(dataframe.columns)
        normalized_columns = [self._normalise_header(column) for column in original_columns]
        if not any(normalized_columns):
            raise ValidationError("Uploaded file has no usable columns")

        if set(_REQUIRED_COLUMNS).issubset(set(normalized_columns)):
            dataframe.columns = normalized_columns
            for column in dataframe.columns:
                if dataframe[column].dtype == object:
                    dataframe[column] = dataframe[column].fillna("").astype(str).str.strip()
            dataframe = dataframe.replace("", pd.NA).dropna(how="all").fillna("")
            return dataframe.reset_index(drop=True)

        account_column = self._match_alias(original_columns, _ACCOUNT_ALIASES)
        debit_column = self._match_alias(original_columns, _DEBIT_ALIASES)
        credit_column = self._match_alias(original_columns, _CREDIT_ALIASES)

        if account_column is None:
            raise ValidationError("account column is required")
        if debit_column is None and credit_column is None:
            raise ValidationError("at least one of debit or credit columns is required")

        normalized = pd.DataFrame()
        normalized["account"] = (
            dataframe[account_column].fillna("").astype(str).str.strip()
        )
        if debit_column is not None:
            normalized["debit"] = self._clean_numeric_series(dataframe[debit_column])
        if credit_column is not None:
            normalized["credit"] = self._clean_numeric_series(dataframe[credit_column])

        if "debit" not in normalized.columns:
            normalized["debit"] = 0.0
        if "credit" not in normalized.columns:
            normalized["credit"] = 0.0

        normalized = normalized.loc[
            ~(
                normalized["account"].eq("")
                & normalized["debit"].fillna(0).eq(0)
                & normalized["credit"].fillna(0).eq(0)
            )
        ]
        normalized["debit"] = normalized["debit"].fillna(0)
        normalized["credit"] = normalized["credit"].fillna(0)
        return normalized.reset_index(drop=True)

    @staticmethod
    def _normalise_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        return text in {"1", "true", "yes", "y"}

    @staticmethod
    def _normalise_row(raw: dict[str, Any], row_number: int) -> dict[str, Any]:
        return {
            "row_number": row_number,
            "group_code": str(raw.get("group_code", "")).strip().upper(),
            "group_name": str(raw.get("group_name", "")).strip(),
            "subgroup_code": str(raw.get("subgroup_code", "")).strip().upper(),
            "subgroup_name": str(raw.get("subgroup_name", "")).strip(),
            "ledger_code": str(raw.get("ledger_code", "")).strip().upper(),
            "ledger_name": str(raw.get("ledger_name", "")).strip(),
            "ledger_type": str(raw.get("ledger_type", "")).strip().upper(),
            "is_control_account": CoaUploadService._normalise_bool(raw.get("is_control_account", False)),
        }

    def parse_file(self, *, file_name: str, file_bytes: bytes) -> list[dict[str, Any]]:
        if len(file_bytes) > _MAX_UPLOAD_BYTES:
            raise ValidationError("File size exceeds 5MB limit")

        lower_name = file_name.lower()
        rows: list[dict[str, Any]] = []

        if lower_name.endswith(".csv"):
            decoded = file_bytes.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))
            for row_number, row in enumerate(reader, start=2):
                rows.append(self._normalise_row(row, row_number))
            return rows

        if lower_name.endswith(".xlsx"):
            workbook = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            worksheet = workbook.active
            values = worksheet.iter_rows(values_only=True)
            headers_row = next(values, None)
            if headers_row is None:
                return []
            headers = [str(item or "").strip() for item in headers_row]
            for row_number, row_values in enumerate(values, start=2):
                raw_row = {headers[index]: row_values[index] for index in range(len(headers))}
                rows.append(self._normalise_row(raw_row, row_number))
            return rows

        raise ValidationError("Only .csv or .xlsx files are supported")

    def validate_structure(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        group_name_by_code: dict[str, str] = {}
        subgroup_group_by_code: dict[str, str] = {}
        ledger_subgroup_by_code: dict[str, str] = {}
        seen_ledger_codes: set[str] = set()

        for row in rows:
            row_errors: list[str] = []
            row_number = int(row["row_number"])

            for column in _REQUIRED_COLUMNS:
                value = row.get(column)
                if value is None or (isinstance(value, str) and not value.strip()):
                    row_errors.append(f"{column} is required")

            ledger_type = str(row.get("ledger_type", "")).upper()
            if ledger_type and ledger_type not in _ALLOWED_LEDGER_TYPES:
                row_errors.append("ledger_type must be one of ASSET, LIABILITY, INCOME, EXPENSE")

            group_code = str(row.get("group_code", ""))
            group_name = str(row.get("group_name", ""))
            if group_code:
                previous_group_name = group_name_by_code.get(group_code)
                if previous_group_name and previous_group_name != group_name:
                    row_errors.append("group_code maps to multiple group_name values")
                group_name_by_code[group_code] = group_name

            subgroup_code = str(row.get("subgroup_code", ""))
            if subgroup_code:
                previous_group_code = subgroup_group_by_code.get(subgroup_code)
                if previous_group_code and previous_group_code != group_code:
                    row_errors.append("subgroup_code must belong to only one group_code")
                subgroup_group_by_code[subgroup_code] = group_code

            ledger_code = str(row.get("ledger_code", ""))
            if ledger_code:
                previous_subgroup = ledger_subgroup_by_code.get(ledger_code)
                if previous_subgroup and previous_subgroup != subgroup_code:
                    row_errors.append("ledger_code must belong to only one subgroup_code")
                if ledger_code in seen_ledger_codes:
                    row_errors.append("duplicate ledger_code in upload")
                ledger_subgroup_by_code[ledger_code] = subgroup_code
                seen_ledger_codes.add(ledger_code)

            if row_errors:
                errors.append(
                    {
                        "row_number": row_number,
                        "errors": row_errors,
                    }
                )

        return errors

    async def validate_only(
        self,
        *,
        file_name: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        try:
            rows = self.parse_file(file_name=file_name, file_bytes=file_bytes)
        except ValidationError:
            normalized_df = self.parse_normalized_dataframe(
                file_name=file_name,
                file_bytes=file_bytes,
            )
            return {
                "total_rows": int(len(normalized_df.index)),
                "valid_rows": int(len(normalized_df.index)),
                "invalid_rows": 0,
                "errors": [],
            }
        errors = self.validate_structure(rows)
        return {
            "total_rows": len(rows),
            "valid_rows": len(rows) - len(errors),
            "invalid_rows": len(errors),
            "errors": errors,
        }

    async def upload(
        self,
        *,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        template_id: uuid.UUID,
        source_type: CoaSourceType,
        upload_mode: CoaUploadMode,
        file_name: str,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        template = (
            await self._session.execute(
                select(CoaIndustryTemplate).where(CoaIndustryTemplate.id == template_id)
            )
        ).scalar_one_or_none()
        if template is None:
            raise NotFoundError("Industry template not found")

        batch = CoaUploadBatch(
            tenant_id=tenant_id,
            template_id=template_id,
            source_type=source_type,
            upload_mode=upload_mode,
            file_name=file_name,
            upload_status=CoaUploadStatus.PROCESSING,
            created_by=actor_id,
        )
        self._session.add(batch)
        await self._session.flush()

        rows = self.parse_file(file_name=file_name, file_bytes=file_bytes)
        errors = self.validate_structure(rows)
        error_map = {int(item["row_number"]): list(item["errors"]) for item in errors}

        if upload_mode != CoaUploadMode.VALIDATE_ONLY:
            staging_payload = []
            for row in rows:
                row_number = int(row["row_number"])
                staging_payload.append(
                    {
                        "batch_id": batch.id,
                        "tenant_id": tenant_id,
                        "template_id": template_id,
                        "row_number": row_number,
                        "group_code": row["group_code"],
                        "group_name": row["group_name"],
                        "subgroup_code": row["subgroup_code"],
                        "subgroup_name": row["subgroup_name"],
                        "ledger_code": row["ledger_code"],
                        "ledger_name": row["ledger_name"],
                        "ledger_type": row["ledger_type"],
                        "is_control_account": bool(row["is_control_account"]),
                        "validation_errors": [{"message": err} for err in error_map.get(row_number, [])] or None,
                        "is_valid": row_number not in error_map,
                    }
                )
            if staging_payload:
                await self._session.execute(insert(CoaUploadStagingRow).values(staging_payload))

        batch.upload_status = CoaUploadStatus.FAILED if errors else CoaUploadStatus.SUCCESS
        batch.error_log = {
            "errors": errors,
            "total_rows": len(rows),
            "valid_rows": len(rows) - len(errors),
            "invalid_rows": len(errors),
        }
        batch.processed_at = datetime.now(UTC)
        await self._session.flush()

        return {
            "batch_id": str(batch.id),
            "upload_status": batch.upload_status.value,
            "total_rows": len(rows),
            "valid_rows": len(rows) - len(errors),
            "invalid_rows": len(errors),
            "errors": errors,
        }

    async def _next_version(
        self,
        *,
        template_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        source_type: CoaSourceType,
    ) -> int:
        max_version = (
            await self._session.execute(
                select(func.max(CoaLedgerAccount.version)).where(
                    CoaLedgerAccount.industry_template_id == template_id,
                    CoaLedgerAccount.source_type == source_type,
                    CoaLedgerAccount.tenant_id.is_(tenant_id)
                    if tenant_id is None
                    else CoaLedgerAccount.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        return int(max_version or 0) + 1

    async def _upsert_groups(
        self,
        *,
        template_id: uuid.UUID,
        rows: list[CoaUploadStagingRow],
    ) -> dict[str, CoaAccountGroup]:
        group_pairs = {(row.group_code, row.group_name) for row in rows}
        group_codes = [item[0] for item in group_pairs]

        existing = (
            await self._session.execute(
                select(CoaAccountGroup).where(
                    CoaAccountGroup.industry_template_id == template_id,
                    CoaAccountGroup.code.in_(group_codes),
                )
            )
        ).scalars().all()
        by_code = {row.code: row for row in existing}

        max_sort = (
            await self._session.execute(
                select(func.max(CoaAccountGroup.sort_order)).where(
                    CoaAccountGroup.industry_template_id == template_id
                )
            )
        ).scalar_one_or_none() or 0

        for code, name in sorted(group_pairs):
            row = by_code.get(code)
            if row is None:
                max_sort += 1
                row = CoaAccountGroup(
                    industry_template_id=template_id,
                    fs_subline_id=None,
                    code=code,
                    name=name,
                    sort_order=int(max_sort),
                    is_active=True,
                )
                self._session.add(row)
                by_code[code] = row
            else:
                row.name = name
                row.is_active = True

        await self._session.flush()
        return by_code

    async def _upsert_subgroups(
        self,
        *,
        groups_by_code: dict[str, CoaAccountGroup],
        rows: list[CoaUploadStagingRow],
    ) -> dict[str, CoaAccountSubgroup]:
        subgroup_pairs = {
            (row.subgroup_code, row.subgroup_name, row.group_code)
            for row in rows
        }

        group_ids = [group.id for group in groups_by_code.values()]
        existing = (
            await self._session.execute(
                select(CoaAccountSubgroup).where(CoaAccountSubgroup.account_group_id.in_(group_ids))
            )
        ).scalars().all()

        by_key = {(row.account_group_id, row.code): row for row in existing}
        max_sort_by_group: dict[uuid.UUID, int] = defaultdict(int)
        for row in existing:
            max_sort_by_group[row.account_group_id] = max(max_sort_by_group[row.account_group_id], row.sort_order)

        by_code: dict[str, CoaAccountSubgroup] = {}
        for subgroup_code, subgroup_name, group_code in sorted(subgroup_pairs):
            group = groups_by_code[group_code]
            key = (group.id, subgroup_code)
            row = by_key.get(key)
            if row is None:
                next_sort = max_sort_by_group[group.id] + 1
                max_sort_by_group[group.id] = next_sort
                row = CoaAccountSubgroup(
                    account_group_id=group.id,
                    code=subgroup_code,
                    name=subgroup_name,
                    sort_order=next_sort,
                    is_active=True,
                )
                self._session.add(row)
                by_key[key] = row
            else:
                row.name = subgroup_name
                row.is_active = True
            by_code[subgroup_code] = row

        await self._session.flush()
        return by_code

    @staticmethod
    def _normal_balance_from_ledger_type(ledger_type: str) -> str:
        if ledger_type in {"ASSET", "EXPENSE"}:
            return "DEBIT"
        return "CREDIT"

    @staticmethod
    def _bspl_from_ledger_type(ledger_type: str) -> str:
        if ledger_type == "INCOME":
            return "REVENUE"
        return ledger_type

    async def _upsert_ledgers(
        self,
        *,
        batch: CoaUploadBatch,
        rows: list[CoaUploadStagingRow],
        subgroups_by_code: dict[str, CoaAccountSubgroup],
    ) -> int:
        if batch.template_id is None:
            raise ValidationError("Batch missing template_id")

        version = await self._next_version(
            template_id=batch.template_id,
            tenant_id=batch.tenant_id,
            source_type=batch.source_type,
        )

        if batch.upload_mode == CoaUploadMode.REPLACE:
            await self._session.execute(
                update(CoaLedgerAccount)
                .where(
                    CoaLedgerAccount.industry_template_id == batch.template_id,
                    CoaLedgerAccount.source_type == batch.source_type,
                    CoaLedgerAccount.tenant_id.is_(batch.tenant_id)
                    if batch.tenant_id is None
                    else CoaLedgerAccount.tenant_id == batch.tenant_id,
                    CoaLedgerAccount.is_active.is_(True),
                )
                .values(is_active=False)
            )

        payload = []
        for idx, row in enumerate(rows, start=1):
            subgroup = subgroups_by_code[row.subgroup_code]
            payload.append(
                {
                    "account_subgroup_id": subgroup.id,
                    "industry_template_id": batch.template_id,
                    "tenant_id": batch.tenant_id,
                    "code": row.ledger_code,
                    "name": row.ledger_name,
                    "description": f"Uploaded via CoA batch {batch.id}",
                    "source_type": batch.source_type,
                    "version": version,
                    "created_by": batch.created_by,
                    "normal_balance": self._normal_balance_from_ledger_type(row.ledger_type),
                    "cash_flow_tag": None,
                    "cash_flow_method": None,
                    "bs_pl_flag": self._bspl_from_ledger_type(row.ledger_type),
                    "asset_liability_class": None,
                    "is_monetary": False,
                    "is_related_party": False,
                    "is_tax_deductible": True,
                    "is_control_account": row.is_control_account,
                    "notes_reference": None,
                    "is_active": True,
                    "sort_order": idx,
                }
            )

        if not payload:
            return 0

        if batch.tenant_id is None:
            await self._session.execute(insert(CoaLedgerAccount).values(payload))
            return len(payload)

        stmt = insert(CoaLedgerAccount).values(payload)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            constraint="uq_coa_ledger_accounts_tenant_code",
            set_={
                "account_subgroup_id": excluded.account_subgroup_id,
                "industry_template_id": excluded.industry_template_id,
                "name": excluded.name,
                "description": excluded.description,
                "source_type": excluded.source_type,
                "version": excluded.version,
                "created_by": excluded.created_by,
                "normal_balance": excluded.normal_balance,
                "cash_flow_tag": excluded.cash_flow_tag,
                "cash_flow_method": excluded.cash_flow_method,
                "bs_pl_flag": excluded.bs_pl_flag,
                "asset_liability_class": excluded.asset_liability_class,
                "is_monetary": excluded.is_monetary,
                "is_related_party": excluded.is_related_party,
                "is_tax_deductible": excluded.is_tax_deductible,
                "is_control_account": excluded.is_control_account,
                "notes_reference": excluded.notes_reference,
                "is_active": True,
                "sort_order": excluded.sort_order,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        return len(payload)

    async def apply_batch(
        self,
        *,
        batch_id: uuid.UUID,
        actor_tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> dict[str, Any]:
        batch = (
            await self._session.execute(
                select(CoaUploadBatch).where(CoaUploadBatch.id == batch_id)
            )
        ).scalar_one_or_none()
        if batch is None:
            raise NotFoundError("CoA upload batch not found")

        if batch.upload_mode == CoaUploadMode.VALIDATE_ONLY:
            raise ValidationError("VALIDATE_ONLY batch cannot be applied")
        if batch.upload_status != CoaUploadStatus.SUCCESS:
            raise ValidationError("Only SUCCESS batches can be applied")

        if batch.source_type == CoaSourceType.ADMIN_TEMPLATE and not is_platform_admin:
            raise AuthorizationError("Only platform admins can apply ADMIN_TEMPLATE batches")

        if batch.source_type == CoaSourceType.TENANT_CUSTOM:
            if batch.tenant_id is None:
                raise ValidationError("Tenant-scoped batch missing tenant_id")
            if batch.tenant_id != actor_tenant_id:
                raise AuthorizationError("Cannot apply another tenant's CoA batch")

        rows = (
            await self._session.execute(
                select(CoaUploadStagingRow)
                .where(
                    CoaUploadStagingRow.batch_id == batch.id,
                    CoaUploadStagingRow.is_valid.is_(True),
                )
                .order_by(CoaUploadStagingRow.row_number.asc())
            )
        ).scalars().all()
        if not rows:
            raise ValidationError("No valid staging rows available for apply")

        groups_by_code = await self._upsert_groups(template_id=batch.template_id, rows=rows)
        subgroups_by_code = await self._upsert_subgroups(groups_by_code=groups_by_code, rows=rows)
        inserted = await self._upsert_ledgers(batch=batch, rows=rows, subgroups_by_code=subgroups_by_code)

        if batch.template_id is None:
            raise ValidationError("Batch missing template_id")

        group_count = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(CoaAccountGroup)
                    .where(
                        CoaAccountGroup.industry_template_id == batch.template_id,
                        CoaAccountGroup.is_active.is_(True),
                    )
                )
            ).scalar_one()
        )
        subgroup_count = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(CoaAccountSubgroup)
                    .join(
                        CoaAccountGroup,
                        CoaAccountSubgroup.account_group_id == CoaAccountGroup.id,
                    )
                    .where(
                        CoaAccountGroup.industry_template_id == batch.template_id,
                        CoaAccountGroup.is_active.is_(True),
                        CoaAccountSubgroup.is_active.is_(True),
                    )
                )
            ).scalar_one()
        )
        ledger_count_stmt = (
            select(func.count())
            .select_from(CoaLedgerAccount)
            .where(
                CoaLedgerAccount.industry_template_id == batch.template_id,
                CoaLedgerAccount.source_type == batch.source_type,
                CoaLedgerAccount.is_active.is_(True),
            )
        )
        if batch.tenant_id is None:
            ledger_count_stmt = ledger_count_stmt.where(CoaLedgerAccount.tenant_id.is_(None))
        else:
            ledger_count_stmt = ledger_count_stmt.where(CoaLedgerAccount.tenant_id == batch.tenant_id)
        ledger_count = int((await self._session.execute(ledger_count_stmt)).scalar_one())

        if group_count <= 0:
            raise ValidationError("CoA apply validation failed: group_count must be > 0")
        if subgroup_count <= 0:
            raise ValidationError("CoA apply validation failed: subgroup_count must be > 0")
        if ledger_count <= 0:
            raise ValidationError("CoA apply validation failed: ledger_count must be > 0")

        log.info(
            "coa_apply_completed upload_id=%s tenant_id=%s ledger_count_inserted=%s",
            batch.id,
            batch.tenant_id,
            inserted,
        )

        batch.processed_at = datetime.now(UTC)
        batch.upload_status = CoaUploadStatus.SUCCESS
        await self._session.flush()

        return {
            "batch_id": str(batch.id),
            "applied_rows": inserted,
            "template_id": str(batch.template_id),
            "source_type": batch.source_type.value,
        }
