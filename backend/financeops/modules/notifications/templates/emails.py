from .base import render_template


def welcome_email(
    full_name: str,
    company_name: str,
    dashboard_url: str = "#",
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = f"Welcome to FinanceOps, {full_name}"
    content = f"""
    <h1>Welcome to FinanceOps, {full_name}!</h1>
    <p>Your account for <strong>{company_name}</strong> is ready.
    You're now set up on India's enterprise finance platform.</p>
    <p>Your next step is to set up two-factor authentication to
    secure your account.</p>
    <p>Once that's done, you can:</p>
    <p>- Import your trial balance or connect your ERP<br>
    - Generate your first MIS report<br>
    - Invite your team members</p>
    <a href="{dashboard_url}" class="btn">Go to Dashboard</a>
    <div class="footer" style="margin-top: 16px;">
      Questions? Email us at support@financeops.in
    </div>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def mfa_setup_required_email(
    full_name: str,
    setup_url: str = "#",
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = "Action required: Set up MFA for your FinanceOps account"
    content = f"""
    <h1>Secure your account with MFA</h1>
    <p>Hi {full_name}, multi-factor authentication is required
    to access FinanceOps. This protects your financial data.</p>
    <a href="{setup_url}" class="btn">Set Up MFA Now</a>
    <div class="warning">
      You won't be able to access the platform until MFA is enabled.
    </div>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def password_reset_email(
    full_name: str,
    reset_url: str,
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = "Reset your FinanceOps password"
    content = f"""
    <h1>Password Reset Request</h1>
    <p>Hi {full_name}, we received a request to reset your password.</p>
    <a href="{reset_url}" class="btn">Reset Password</a>
    <p>This link expires in 15 minutes.</p>
    <div class="warning">
      If you didn't request this, ignore this email.
      Your password will not change.
    </div>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def board_pack_ready_email(
    recipient_name: str,
    period: str,
    entity_name: str,
    board_pack_url: str,
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = f"Board Pack Ready - {entity_name} {period}"
    content = f"""
    <h1>Board Pack is Ready</h1>
    <p>Hi {recipient_name}, the board pack for
    <strong>{entity_name}</strong> for period
    <strong>{period}</strong> has been generated and
    is ready for your review.</p>
    <a href="{board_pack_url}" class="btn">View Board Pack</a>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def covenant_breach_email(
    recipient_name: str,
    covenant_label: str,
    facility_name: str,
    actual_value: str,
    threshold_value: str,
    breach_type: str,
    covenants_url: str = "#",
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    is_breach = breach_type == "breach"
    subject = (
        f"URGENT: Covenant breach - {covenant_label}"
        if is_breach
        else f"Warning: Covenant near breach - {covenant_label}"
    )
    content = f"""
    <h1>Covenant {"Breach" if is_breach else "Near Breach"} Alert</h1>
    <p>Hi {recipient_name}, a covenant threshold has been
    {"breached" if is_breach else "approached"} for
    <strong>{facility_name}</strong>.</p>
    <div class="warning">
      <strong>{covenant_label}</strong><br>
      Actual: {actual_value} |
      Threshold: {threshold_value}
    </div>
    <p>Please review immediately and contact your lender
    if necessary.</p>
    <a href="{covenants_url}" class="btn">View Covenants</a>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def signoff_request_email(
    signatory_name: str,
    document_reference: str,
    period: str,
    signoff_url: str,
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = f"Signature required: {document_reference} - {period}"
    content = f"""
    <h1>Your Signature is Required</h1>
    <p>Hi {signatory_name}, a document requires your
    digital signature.</p>
    <p><strong>Document:</strong> {document_reference}<br>
    <strong>Period:</strong> {period}</p>
    <a href="{signoff_url}" class="btn">Review & Sign</a>
    <div class="warning">
      This is a legally binding digital signature requiring
      MFA verification.
    </div>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def auditor_access_email(
    auditor_name: str,
    engagement_name: str,
    portal_url: str,
    access_token: str,
    valid_until: str,
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = f"Auditor Portal Access - {engagement_name}"
    content = f"""
    <h1>Auditor Portal Access Granted</h1>
    <p>Hi {auditor_name}, you have been granted access to the
    FinanceOps Auditor Portal for:
    <strong>{engagement_name}</strong></p>
    <p><strong>Portal URL:</strong><br>
    <a href="{portal_url}" style="color: #60a5fa;">{portal_url}</a></p>
    <p><strong>Your Access Token:</strong></p>
    <span class="code">{access_token}</span>
    <div class="warning">
      Copy this token - it will not be shown again.
      Valid until: {valid_until}
    </div>
    <a href="{portal_url}" class="btn">Open Auditor Portal</a>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)


def user_invited_email(
    invitee_name: str,
    inviter_name: str,
    company_name: str,
    invite_url: str,
    unsubscribe_url: str = "#",
) -> tuple[str, str]:
    subject = f"You've been invited to FinanceOps - {company_name}"
    content = f"""
    <h1>You've been invited to join FinanceOps</h1>
    <p>Hi {invitee_name}, <strong>{inviter_name}</strong> has
    invited you to join <strong>{company_name}</strong> on
    FinanceOps.</p>
    <a href="{invite_url}" class="btn">Accept Invitation</a>
    <p>This invitation expires in 48 hours.</p>
    """
    return subject, render_template(content, unsubscribe_url=unsubscribe_url)
