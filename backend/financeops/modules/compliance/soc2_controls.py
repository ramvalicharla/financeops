from __future__ import annotations

from typing import TypedDict


class SOC2Control(TypedDict):
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
) -> SOC2Control:
    return {
        "control_id": control_id,
        "control_name": name,
        "control_description": description,
        "category": category,
        "auto_evaluable": auto_check_function is not None,
        "auto_check_function": auto_check_function,
    }


SOC2_CONTROLS: list[SOC2Control] = [
    _control("CC1.1", "CC1", "Control Environment Oversight", "The organization demonstrates commitment to integrity and ethical values."),
    _control("CC1.2", "CC1", "Board Independence", "The board of directors demonstrates independence from management."),
    _control("CC1.3", "CC1", "Management Structure", "Management establishes structures, reporting lines, and authority."),
    _control("CC1.4", "CC1", "Qualified Personnel", "The organization attracts, develops, and retains competent people."),
    _control("CC1.5", "CC1", "Accountability", "Individuals are held accountable for internal control responsibilities."),
    _control("CC2.1", "CC2", "Information Quality", "Relevant and quality information supports internal control."),
    _control("CC2.2", "CC2", "Communication Internally", "Information is communicated internally."),
    _control("CC2.3", "CC2", "Communication Externally", "Information is communicated with external parties."),
    _control("CC3.1", "CC3", "Risk Identification", "Risks to objectives are identified and analyzed."),
    _control("CC3.2", "CC3", "Fraud Risk", "Fraud risk considerations are integrated into risk assessment."),
    _control("CC3.3", "CC3", "Significant Change", "Significant changes are identified and assessed."),
    _control("CC3.4", "CC3", "Risk Response", "Responses to identified risks are selected and developed."),
    _control("CC4.1", "CC4", "Monitoring Activities", "The organization selects and develops monitoring activities."),
    _control("CC4.2", "CC4", "Deficiency Evaluation", "Internal control deficiencies are evaluated and communicated."),
    _control("CC5.1", "CC5", "Control Activities Selection", "Control activities mitigate risks to acceptable levels."),
    _control("CC5.2", "CC5", "Technology Controls", "General controls over technology support objectives."),
    _control("CC5.3", "CC5", "Policy and Procedure Deployment", "Control activities are deployed through policies and procedures."),
    _control("CC6.1", "CC6", "Logical Access Restriction", "Logical access controls are implemented and enforced.", auto_check_function="check_cc6_1_rls"),
    _control("CC6.2", "CC6", "Access Deprovisioning", "Access is removed in a timely manner when no longer required.", auto_check_function="check_cc6_2_offboarding"),
    _control("CC6.3", "CC6", "Role-Based Access", "Access rights are authorized based on business needs."),
    _control("CC6.4", "CC6", "Privileged Access", "Privileged access is controlled, reviewed, and monitored."),
    _control("CC6.5", "CC6", "Authentication Controls", "Authentication mechanisms verify user identities."),
    _control("CC6.6", "CC6", "MFA Enforcement", "Multi-factor authentication protects high-risk access.", auto_check_function="check_cc6_6_mfa"),
    _control("CC6.7", "CC6", "Data Transmission Protection", "Transmission of confidential data is protected."),
    _control("CC6.8", "CC6", "Boundary Protection", "System boundaries are protected from unauthorized access."),
    _control("CC7.1", "CC7", "Malware Detection", "Malware detection and prevention controls are active.", auto_check_function="check_cc7_1_clamav"),
    _control("CC7.2", "CC7", "Monitoring and Alerting", "Security events are monitored and responded to."),
    _control("CC7.3", "CC7", "Incident Response", "Incident response procedures are defined and exercised."),
    _control("CC7.4", "CC7", "Vulnerability Management", "Vulnerabilities are identified and remediated promptly."),
    _control("CC7.5", "CC7", "Change Monitoring", "Changes are tracked and monitored for unauthorized activity."),
    _control("CC8.1", "CC8", "Change Management Governance", "Changes are authorized, tested, approved, and documented.", auto_check_function="check_cc8_1_migrations"),
    _control("CC9.1", "CC9", "Business Continuity", "Business continuity and disaster recovery are planned and tested."),
    _control("A1.1", "A", "Availability Commitments", "Availability commitments are defined and monitored.", auto_check_function="check_a1_1_health"),
    _control("A1.2", "A", "Capacity Monitoring", "Capacity and performance are monitored to meet targets."),
    _control("A1.3", "A", "Recovery Capability", "Recovery capability supports availability commitments."),
    _control("C1.1", "C", "Confidentiality Commitments", "Confidentiality commitments are documented and maintained."),
    _control("C1.2", "C", "Data Erasure Readiness", "Confidential data can be removed or rendered inaccessible.", auto_check_function="check_c1_2_erasure"),
    _control("PI1.1", "PI", "Input Validation", "Input data is complete, accurate, and authorized."),
    _control("PI1.2", "PI", "Processing Integrity", "Data processing is complete, valid, and timely."),
    _control("PI1.3", "PI", "Output Validation", "System output is complete, accurate, and distributed appropriately."),
    _control("PI1.4", "PI", "Error Detection", "Processing errors are detected and handled."),
    _control("PI1.5", "PI", "Data Retention Integrity", "Retention and disposal support processing integrity commitments."),
    _control("P1.1", "P", "Privacy Notice", "Privacy notices are provided and maintained."),
    _control("P2.1", "P", "Choice and Consent", "Privacy choices and consent are captured and enforced."),
    _control("P3.1", "P", "Collection Limitation", "Personal information collection is limited to stated purposes."),
    _control("P4.1", "P", "Use Limitation", "Use, retention, and disclosure are limited to objectives."),
    _control("P8.1", "P", "Privacy Monitoring", "Privacy-related controls are monitored and evaluated."),
]


__all__ = ["SOC2_CONTROLS", "SOC2Control"]
