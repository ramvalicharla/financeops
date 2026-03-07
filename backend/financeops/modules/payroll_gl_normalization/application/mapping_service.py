from __future__ import annotations

from typing import Any

from financeops.utils.determinism import canonical_json_dumps, sha256_hex_text


PAYROLL_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "employee_code": ("employee_code", "employee id", "emp code", "emp_id"),
    "employee_name": ("employee_name", "employee", "name", "emp name"),
    "legal_entity": ("legal_entity", "entity", "company"),
    "department": ("department", "dept"),
    "cost_center": ("cost_center", "cost centre", "cc"),
    "business_unit": ("business_unit", "bu"),
    "location": ("location", "site"),
    "grade": ("grade",),
    "designation": ("designation", "title"),
    "currency_code": ("currency", "currency_code"),
    "basic_pay": ("basic", "basic_pay"),
    "hra": ("hra",),
    "allowances": ("allowance", "allowances"),
    "bonus": ("bonus",),
    "commission": ("commission",),
    "overtime": ("overtime", "ot"),
    "employer_pf": ("employer_pf", "employer pf"),
    "employer_esi": ("employer_esi", "employer esi"),
    "gratuity_provision": ("gratuity", "gratuity_provision"),
    "leave_encashment": ("leave encashment", "leave_encashment"),
    "payroll_tax": ("payroll_tax", "tax"),
    "employee_pf": ("employee_pf", "employee pf"),
    "employee_esi": ("employee_esi", "employee esi"),
    "loan_deduction": ("loan", "loan_deduction"),
    "other_deductions": ("other deductions", "other_deductions"),
    "gross_pay": ("gross", "gross_pay"),
    "total_deductions": ("total deductions", "total_deductions"),
    "employer_total_cost": ("employer total cost", "ctc"),
    "net_pay": ("net", "net_pay"),
}

GL_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "journal_id": ("journal id", "journal_id", "voucher"),
    "journal_line_no": ("line no", "line_no", "journal_line_no"),
    "posting_date": ("posting date", "posting_date"),
    "document_date": ("document date", "document_date"),
    "posting_period": ("posting period", "period"),
    "legal_entity": ("legal entity", "entity"),
    "account_code": ("account code", "account", "gl code"),
    "account_name": ("account name", "account description"),
    "cost_center": ("cost center", "cost centre"),
    "department": ("department", "dept"),
    "business_unit": ("business unit", "bu"),
    "project": ("project",),
    "customer": ("customer",),
    "vendor": ("vendor", "supplier"),
    "source_module": ("source module", "module"),
    "source_document_id": ("source doc id", "document id", "doc id"),
    "currency_code": ("currency", "currency_code"),
    "debit_amount": ("debit", "debit_amount"),
    "credit_amount": ("credit", "credit_amount"),
    "signed_amount": ("signed_amount", "amount"),
    "local_amount": ("local_amount",),
    "transaction_amount": ("transaction_amount", "txn_amount"),
}


class MappingService:
    def propose_mappings(self, *, source_family: str, headers: list[str]) -> list[dict[str, Any]]:
        alias_map = PAYROLL_FIELD_ALIASES if source_family == "payroll" else GL_FIELD_ALIASES
        mappings: list[dict[str, Any]] = []
        for header in headers:
            canonical = self._resolve_alias(alias_map, header)
            if canonical is None:
                continue
            mapping_type = self._mapping_type(source_family=source_family, canonical=canonical)
            mappings.append(
                {
                    "mapping_type": mapping_type,
                    "source_field_name": header,
                    "canonical_field_name": canonical,
                    "transform_rule": self._default_transform(canonical),
                    "default_value_json": {},
                    "required_flag": canonical in self._required_fields(source_family),
                    "confidence_score": "1.0000",
                }
            )
        mappings.sort(key=lambda item: (item["mapping_type"], item["source_field_name"]))
        return mappings

    def mapping_version_token(self, mappings: list[dict[str, Any]]) -> str:
        return sha256_hex_text(canonical_json_dumps(mappings))

    def unmapped_headers(self, *, headers: list[str], mappings: list[dict[str, Any]]) -> list[str]:
        mapped = {item["source_field_name"] for item in mappings}
        return sorted(header for header in headers if header not in mapped)

    def _resolve_alias(
        self, alias_map: dict[str, tuple[str, ...]], header: str
    ) -> str | None:
        norm = header.strip().lower().replace("_", " ")
        for canonical, aliases in alias_map.items():
            if norm == canonical.replace("_", " "):
                return canonical
            for alias in aliases:
                alias_norm = alias.strip().lower().replace("_", " ")
                if alias_norm in norm or norm in alias_norm:
                    return canonical
        return None

    def _mapping_type(self, *, source_family: str, canonical: str) -> str:
        dimension_fields = {
            "employee_code",
            "employee_name",
            "legal_entity",
            "department",
            "cost_center",
            "business_unit",
            "location",
            "grade",
            "designation",
            "currency_code",
            "journal_id",
            "journal_line_no",
            "posting_date",
            "document_date",
            "posting_period",
            "account_code",
            "account_name",
            "project",
            "customer",
            "vendor",
            "source_module",
            "source_document_id",
        }
        if source_family == "payroll":
            return "payroll_dimension" if canonical in dimension_fields else "payroll_metric"
        return "gl_dimension" if canonical in dimension_fields else "gl_metric"

    def _required_fields(self, source_family: str) -> set[str]:
        if source_family == "payroll":
            return {"employee_code", "employee_name", "currency_code"}
        return {"account_code", "currency_code"}

    def _default_transform(self, canonical: str) -> str | None:
        if canonical in {"account_code", "currency_code"}:
            return "uppercase"
        if canonical.endswith("_date"):
            return "date_parse"
        if canonical.endswith("_amount") or canonical in {"gross_pay", "net_pay"}:
            return "numeric_parse"
        return None
