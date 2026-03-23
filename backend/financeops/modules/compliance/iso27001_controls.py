from __future__ import annotations

from typing import TypedDict


class ISOControl(TypedDict):
    control_id: str
    control_name: str
    control_description: str
    category: str
    auto_evaluable: bool
    auto_check_function: str | None


def _control(
    control_id: str,
    category: str,
    name: str,
    description: str,
    *,
    auto_check_function: str | None = None,
) -> ISOControl:
    return {
        "control_id": control_id,
        "control_name": name,
        "control_description": description,
        "category": category,
        "auto_evaluable": auto_check_function is not None,
        "auto_check_function": auto_check_function,
    }


ISO27001_CONTROLS: list[ISOControl] = [
    _control("A.5.1.1", "A.5", "Information Security Policies", "Policies for information security are defined, approved, and communicated."),
    _control("A.5.1.2", "A.5", "Policy Review", "Information security policies are reviewed at planned intervals."),
    _control("A.5.1.3", "A.5", "Topic-Specific Policies", "Topic-specific policies are established where needed."),
    _control("A.6.1.1", "A.6", "Information Security Roles", "Roles and responsibilities are defined and assigned."),
    _control("A.6.1.2", "A.6", "Segregation of Duties", "Conflicting duties are segregated to reduce misuse risk."),
    _control("A.8.1.1", "A.8", "Asset Inventory", "Assets are identified and inventoried."),
    _control("A.8.1.2", "A.8", "Asset Ownership", "Assets have assigned owners."),
    _control("A.8.2.1", "A.8", "Information Classification", "Information is classified according to legal and business needs."),
    _control("A.9.1.1", "A.9", "Access Control Policy", "An access control policy is established and maintained."),
    _control("A.9.2.1", "A.9", "User Registration and Deregistration", "Formal process manages user lifecycle."),
    _control("A.9.2.3", "A.9", "Privilege Management", "Privileged rights allocation and use is restricted."),
    _control("A.9.2.5", "A.9", "Review of Access Rights", "Access rights are reviewed regularly."),
    _control("A.9.2.6", "A.9", "Removal or Adjustment of Access Rights", "Access rights are removed when no longer required.", auto_check_function="check_cc6_2_offboarding"),
    _control("A.9.4.2", "A.9", "Secure Log-on Procedures", "Secure log-on enforces strong authentication.", auto_check_function="check_cc6_6_mfa"),
    _control("A.10.1.1", "A.10", "Policy on Cryptographic Controls", "Cryptographic controls are defined and managed.", auto_check_function="check_a10_1_1_encryption"),
    _control("A.10.1.2", "A.10", "Key Management", "Cryptographic keys are managed through their lifecycle.", auto_check_function="check_a10_1_2_key_rotation"),
    _control("A.12.1.1", "A.12", "Documented Operating Procedures", "Operating procedures are documented and maintained."),
    _control("A.12.1.2", "A.12", "Change Management", "Changes to systems are controlled."),
    _control("A.12.2.1", "A.12", "Controls Against Malware", "Detection and prevention controls protect against malware.", auto_check_function="check_cc7_1_clamav"),
    _control("A.12.3.1", "A.12", "Information Backup", "Backup copies are created, protected, and tested.", auto_check_function="check_a12_3_1_backup"),
    _control("A.12.4.1", "A.12", "Event Logging", "Event logs record user and system activity.", auto_check_function="check_a12_4_1_chain_hash"),
    _control("A.12.6.1", "A.12", "Technical Vulnerability Management", "Technical vulnerabilities are managed in a timely manner."),
    _control("A.13.1.1", "A.13", "Network Controls", "Networks are managed and controlled to protect information."),
    _control("A.13.2.1", "A.13", "Information Transfer Policies", "Information transfer policies and controls are established."),
    _control("A.14.1.1", "A.14", "Security Requirements of Information Systems", "Security requirements are included in system lifecycle."),
    _control("A.14.2.5", "A.14", "Secure System Engineering Principles", "Secure engineering principles are established and applied."),
    _control("A.16.1.1", "A.16", "Incident Responsibilities and Procedures", "Incident response responsibilities and procedures are established."),
    _control("A.16.1.4", "A.16", "Assessment and Decision on Events", "Information security events are assessed and classified."),
    _control("A.16.1.7", "A.16", "Collection of Evidence", "Evidence is collected and preserved for investigation."),
    _control("A.17.1.1", "A.17", "Business Continuity Planning", "Business continuity is planned to protect information assets."),
    _control("A.17.2.1", "A.17", "Availability of Information Processing Facilities", "Information processing facilities are resilient."),
    _control("A.18.1.1", "A.18", "Identification of Applicable Legislation", "Relevant legal and contractual requirements are identified."),
    _control("A.18.1.2", "A.18", "Intellectual Property Rights", "Procedures ensure compliance with IPR requirements."),
    _control("A.18.1.4", "A.18", "Privacy and Protection of PII", "Privacy and PII controls are implemented.", auto_check_function="check_c1_2_erasure"),
    _control("A.18.2.1", "A.18", "Independent Review of Information Security", "Information security approach is independently reviewed."),
]


__all__ = ["ISO27001_CONTROLS", "ISOControl"]
