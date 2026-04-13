import { describe, expect, it } from "vitest"

import {
  getSafeCallbackUrl,
  isLoginTokenPayload,
  type BackendLoginPayload,
} from "../../lib/login-flow"

describe("login flow helpers", () => {
  it("accepts only local callback URLs", () => {
    expect(getSafeCallbackUrl("/dashboard/cfo")).toBe("/dashboard/cfo")
    expect(getSafeCallbackUrl("https://malicious.example")).toBe("/orgs")
    expect(getSafeCallbackUrl("//malicious.example")).toBe("/orgs")
    expect(getSafeCallbackUrl("dashboard")).toBe("/orgs")
    expect(getSafeCallbackUrl(null)).toBe("/orgs")
  })

  it("detects token payloads returned by backend login", () => {
    const tokenPayload: BackendLoginPayload = {
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    }
    const challengePayload: BackendLoginPayload = {
      requires_mfa: true,
      mfa_challenge_token: "challenge",
    }

    expect(isLoginTokenPayload(tokenPayload)).toBe(true)
    expect(isLoginTokenPayload(challengePayload)).toBe(false)
  })
})
