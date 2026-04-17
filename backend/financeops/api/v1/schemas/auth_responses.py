from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr


class EntityRoleSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entity_id: str
    entity_name: str
    role: str
    currency: str


class UserSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: EmailStr
    full_name: str | None = None
    role: str
    is_active: bool
    mfa_enabled: bool


class TenantSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tenant_id: str
    display_name: str
    slug: str | None = None
    tenant_type: str | None = None
    country: str | None = None
    timezone: str | None = None
    status: str | None = None
    org_setup_complete: bool | None = None
    org_setup_step: int | None = None
    coa_status: str | None = None
    onboarding_score: int | None = None


class BillingPlanSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None
    plan_tier: str
    pricing_type: str | None = None
    price: str | None = None
    currency: str | None = None


class BillingSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subscription_id: str
    plan_id: str
    status: str
    plan: BillingPlanSchema | None = None


class RegisterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    tenant_id: str
    status: str
    setup_token: str
    mfa_setup_required: bool


class TokenPairResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginMfaChallengeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requires_mfa: Literal[True] = True
    mfa_challenge_token: str


class LoginPasswordChangeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requires_password_change: Literal[True] = True
    password_change_token: str
    status: str | None = None


class LoginMfaSetupResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requires_mfa_setup: Literal[True] = True
    setup_token: str
    status: str | None = None


LoginResponse = (
    TokenPairResponse
    | LoginMfaChallengeResponse
    | LoginPasswordChangeResponse
    | LoginMfaSetupResponse
)


class MfaSetupResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    secret: str
    qr_url: str


class MfaVerifySetupResponse(TokenPairResponse):
    model_config = ConfigDict(extra="ignore")

    status: str
    recovery_codes: list[str]


class ChangePasswordSuccessResponse(TokenPairResponse):
    model_config = ConfigDict(extra="ignore")

    status: str


ChangePasswordResponse = ChangePasswordSuccessResponse


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    logged_out: bool


class RevokeAllSessionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    revoked_sessions: int


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    email: EmailStr
    full_name: str | None = None
    role: str
    mfa_enabled: bool
    is_active: bool
    created_at: str
    tenant: TenantSchema
    billing: BillingSchema | None = None
    entity_roles: list[EntityRoleSchema]


class RawBillingPayloadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    billing: dict[str, Any]
