from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PIIPattern:
    name: str
    pattern: re.Pattern[str]
    replacement: str
    priority: int  # lower = masked first


PII_PATTERNS: list[PIIPattern] = [
    PIIPattern(
        name="email",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        ),
        replacement="[EMAIL]",
        priority=1,
    ),
    PIIPattern(
        name="phone_india",
        pattern=re.compile(r"(?<!\d)(?:\+91|0)?[6-9]\d{9}(?!\d)"),
        replacement="[PHONE]",
        priority=2,
    ),
    # Require explicit separator/space to avoid masking plain amounts like 50000.
    PIIPattern(
        name="phone_international",
        pattern=re.compile(r"\+\d[\d\-\s]{7,}\d"),
        replacement="[PHONE]",
        priority=2,
    ),
    PIIPattern(
        name="pan_india",
        pattern=re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
        replacement="[PAN]",
        priority=1,
    ),
    PIIPattern(
        name="aadhar_india",
        pattern=re.compile(r"(?<![+\d])\d{4}\s\d{4}\s\d{4}(?!\d)"),
        replacement="[AADHAR]",
        priority=1,
    ),
    PIIPattern(
        name="gstin_india",
        pattern=re.compile(
            r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"
        ),
        replacement="[GSTIN]",
        priority=2,
    ),
    PIIPattern(
        name="account_number",
        pattern=re.compile(r"\b\d{9,18}\b"),
        replacement="[ACCT_NUM]",
        priority=3,
    ),
    PIIPattern(
        name="ifsc_code",
        pattern=re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        replacement="[IFSC]",
        priority=2,
    ),
]
