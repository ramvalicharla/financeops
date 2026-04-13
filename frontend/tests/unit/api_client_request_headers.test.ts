import { beforeEach, describe, expect, it, vi } from "vitest"
import { AxiosHeaders, type InternalAxiosRequestConfig } from "axios"

const getSessionMock = vi.fn()

vi.mock("next-auth/react", async () => {
  const actual = await vi.importActual<typeof import("next-auth/react")>("next-auth/react")
  return {
    ...actual,
    getSession: (...args: unknown[]) => getSessionMock(...args),
    signOut: vi.fn(),
  }
})

describe("api client request headers", () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000")
    getSessionMock.mockReset()
  })

  it("adds Authorization header from the NextAuth accessToken alias", async () => {
    getSessionMock.mockResolvedValue({ accessToken: "backend-jwt-token" })

    const { setAuthHeaders } = await import("../../lib/api/client")
    const { resetApiSessionCacheForTests } = await import("../../lib/api/session-cache")
    resetApiSessionCacheForTests()

    const config = {
      headers: new AxiosHeaders(),
      method: "get",
    } as InternalAxiosRequestConfig

    await setAuthHeaders(config)

    expect(config.headers.get("Authorization")).toBe("Bearer backend-jwt-token")
  })
})
