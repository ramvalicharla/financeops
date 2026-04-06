import { describe, expect, it } from "vitest"

import { shouldSignOutOnUnauthorized } from "../../lib/api/auth-unauthorized"

describe("api client auth handling", () => {
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
})
