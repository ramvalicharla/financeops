export type LoginTokenPayload = {
  access_token: string
  refresh_token: string
  token_type: string
}

export type LoginChallengePayload = {
  requires_mfa: true
  mfa_challenge_token: string
}

export type LoginPasswordChangePayload = {
  requires_password_change: true
  password_change_token: string
  status?: string
}

export type LoginMFASetupPayload = {
  requires_mfa_setup: true
  setup_token: string
  status?: string
}

export type BackendLoginPayload =
  | LoginTokenPayload
  | LoginChallengePayload
  | LoginPasswordChangePayload
  | LoginMFASetupPayload

export const isLoginTokenPayload = (
  payload: BackendLoginPayload,
): payload is LoginTokenPayload =>
  "access_token" in payload &&
  "refresh_token" in payload &&
  typeof payload.access_token === "string" &&
  typeof payload.refresh_token === "string"

export const getSafeCallbackUrl = (
  rawCallbackUrl: string | null | undefined,
  fallback = "/orgs",
): string => {
  if (!rawCallbackUrl) {
    return fallback
  }
  if (!rawCallbackUrl.startsWith("/") || rawCallbackUrl.startsWith("//")) {
    return fallback
  }
  return rawCallbackUrl
}
