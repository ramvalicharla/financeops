import { describe, expect, it, vi } from "vitest"

describe("auth secret resolution", () => {
  it("prefers NEXTAUTH_SECRET", async () => {
    vi.resetModules()
    vi.stubEnv("NEXTAUTH_SECRET", "nextauth-secret")
    vi.stubEnv("AUTH_SECRET", "auth-secret")

    const { getAuthSecret } = await import("../../lib/auth-secret")
    expect(getAuthSecret()).toBe("nextauth-secret")
  })

  it("falls back to AUTH_SECRET", async () => {
    vi.resetModules()
    vi.unstubAllEnvs()
    vi.stubEnv("AUTH_SECRET", "auth-secret")

    const { getAuthSecret } = await import("../../lib/auth-secret")
    expect(getAuthSecret()).toBe("auth-secret")
  })
})
