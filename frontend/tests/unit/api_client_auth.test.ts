import { beforeEach, describe, expect, it, vi } from "vitest"

import { shouldSignOutOnUnauthorized } from "../../lib/api/auth-unauthorized"
import {
  readSessionForApi,
  resetApiSessionCacheForTests,
} from "../../lib/api/session-cache"

const getSessionMock = vi.fn()

vi.mock("next-auth/react", async () => {
  const actual = await vi.importActual<typeof import("next-auth/react")>("next-auth/react")
  return {
    ...actual,
    getSession: (...args: unknown[]) => getSessionMock(...args),
    signOut: vi.fn(),
  }
})

describe("api client auth handling", () => {
  beforeEach(() => {
    resetApiSessionCacheForTests()
    getSessionMock.mockReset()
  })

  it("does not sign out on auth bootstrap 401 responses", () => {
    expect(
      shouldSignOutOnUnauthorized({
        config: {
          url: "/api/v1/auth/login",
          headers: { Authorization: "Bearer test-token" },
        },
        response: { status: 401 },
      }, ""),
    ).toBe(false)
  })

  it("does not sign out when the request was anonymous", () => {
    expect(
      shouldSignOutOnUnauthorized({
        config: {
          url: "/api/v1/sync/runs",
          headers: {},
        },
        response: { status: 401 },
      }, ""),
    ).toBe(false)
  })

  it("signs out on protected API 401 responses with an auth header", () => {
    expect(
      shouldSignOutOnUnauthorized({
        config: {
          url: "/api/v1/sync/runs",
          headers: { Authorization: "Bearer test-token" },
        },
        response: { status: 401 },
      }, ""),
    ).toBe(true)
  })

  it("does not sign out on control-plane token 401 responses", () => {
    expect(
      shouldSignOutOnUnauthorized({
        config: {
          url: "/api/v1/erp/connectors",
          headers: { Authorization: "Bearer test-token" },
        },
        response: {
          status: 401,
          data: {
            error: {
              code: "authentication_error",
              message: "CONTROL_PLANE_CONTEXT_REQUIRED",
            },
          },
        },
      }, ""),
    ).toBe(false)
  })

  it("deduplicates concurrent session reads for API calls", async () => {
    getSessionMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ access_token: "token-1" }), 10)
        }),
    )

    const [first, second, third] = await Promise.all([
      readSessionForApi(),
      readSessionForApi(),
      readSessionForApi(),
    ])

    expect(first).toEqual({ access_token: "token-1" })
    expect(second).toEqual({ access_token: "token-1" })
    expect(third).toEqual({ access_token: "token-1" })
    expect(getSessionMock).toHaveBeenCalledTimes(1)
  })
})
