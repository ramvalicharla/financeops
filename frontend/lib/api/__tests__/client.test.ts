/**
 * Tests for the axios response interceptor in lib/api/client.ts.
 *
 * Focus: hotfix 1.1.5 — the 403/ORG_SETUP_REQUIRED recovery path must read
 * active_entity_id from workspaceStore.entityId (canonical), not from the
 * deprecated tenantStore.active_entity_id.
 *
 * Test strategy: invoke the response interceptor's error handler directly.
 * Going through the full HTTP pipeline fails in this environment because
 * BASE_URL is empty (NEXT_PUBLIC_API_URL not set), which causes the request
 * interceptor to throw before the adapter fires. Direct invocation is more
 * appropriate for testing interceptor logic in isolation anyway.
 */

import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest"
import type { Mock } from "vitest"
import axios, { AxiosError } from "axios"
import type { InternalAxiosRequestConfig, AxiosResponse } from "axios"

// ── Store mocks (hoisted — must appear before any import that reads the module) ─

vi.mock("@/lib/store/tenant", () => ({
  useTenantStore: { getState: vi.fn() },
}))

vi.mock("@/lib/store/workspace", () => ({
  useWorkspaceStore: { getState: vi.fn() },
}))

vi.mock("@/lib/store/location", () => ({
  useLocationStore: { getState: vi.fn().mockReturnValue({ active_location_id: null }) },
}))

vi.mock("@/lib/store/ui", () => ({
  useUIStore: {
    getState: vi.fn().mockReturnValue({ setBillingWarning: vi.fn() }),
  },
}))

// ── External dependency mocks ────────────────────────────────────────────────

vi.mock("next-auth/react", () => ({ signOut: vi.fn() }))

vi.mock("@/lib/api/auth-unauthorized", () => ({
  shouldSignOutOnUnauthorized: vi.fn().mockReturnValue(false),
}))

vi.mock("@/lib/api/auth-loop-guard", () => ({
  consumeAuthRecoveryAttempt: vi.fn().mockReturnValue(false),
}))

vi.mock("@/lib/api/session-cache", () => ({
  readSessionForApi: vi.fn().mockResolvedValue(null),
}))

vi.mock("@sentry/browser", () => ({
  captureException: vi.fn(),
}))

// ── Import SUT after mocks are in place ─────────────────────────────────────

import apiClient from "../client"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"

// ── Helper: get the registered response interceptor error handler ────────────
// Axios stores interceptors in an internal array of { fulfilled, rejected } pairs.
type InterceptorManager = { handlers: Array<{ fulfilled?: unknown; rejected?: (e: unknown) => unknown } | null> }

function getResponseErrorHandler(): (error: unknown) => Promise<unknown> {
  const mgr = (apiClient.interceptors.response as unknown as InterceptorManager)
  const handler = mgr.handlers.find((h) => h !== null && typeof h?.rejected === "function")
  if (!handler?.rejected) throw new Error("No response error interceptor found on apiClient")
  return handler.rejected as (error: unknown) => Promise<unknown>
}

// ── Helper: build an AxiosError that matches 403/ORG_SETUP_REQUIRED ──────────

function make403OrgSetupError(currentStep = 3): AxiosError {
  const config = { headers: axios.defaults.headers } as unknown as InternalAxiosRequestConfig
  const responseData = {
    error: {
      code: "ORG_SETUP_REQUIRED",
      message: "Org setup required",
      details: { current_step: currentStep },
    },
  }
  const response = {
    data: responseData,
    status: 403,
    statusText: "Forbidden",
    headers: {},
    config,
  } as unknown as AxiosResponse
  return new AxiosError("Forbidden", "ERR_BAD_RESPONSE", config, {}, response)
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("client.ts interceptor — 403 ORG_SETUP_REQUIRED recovery", () => {
  let interceptorErrorHandler: (error: unknown) => Promise<unknown>
  const mockSetTenant = vi.fn()

  beforeAll(() => {
    interceptorErrorHandler = getResponseErrorHandler()
  })

  beforeEach(() => {
    vi.clearAllMocks()

    // tenantStore: has stale active_entity_id and valid tenant creds
    ;(useTenantStore.getState as Mock).mockReturnValue({
      tenant_id: "tenant-001",
      tenant_slug: "acme",
      org_setup_complete: false,
      org_setup_step: 1,
      entity_roles: [],
      active_entity_id: "stale-entity-id",
      is_switched: false,
      setTenant: mockSetTenant,
    })

    // workspaceStore: canonical, up-to-date entityId
    ;(useWorkspaceStore.getState as Mock).mockReturnValue({
      entityId: "fresh-entity-id",
      orgId: "org-001",
    })
  })

  it("calls setTenant with active_entity_id from workspaceStore.entityId (not tenantStore.active_entity_id)", async () => {
    await expect(interceptorErrorHandler(make403OrgSetupError(3))).rejects.toThrow()

    expect(mockSetTenant).toHaveBeenCalledOnce()
    const payload = mockSetTenant.mock.calls[0][0] as Record<string, unknown>

    // Hotfix 1.1.5 assertion: must be the canonical workspaceStore value
    expect(payload.active_entity_id).toBe("fresh-entity-id")

    // Regression guard: must NOT be the deprecated tenantStore value
    expect(payload.active_entity_id).not.toBe("stale-entity-id")
  })

  it("preserves org_setup_step from 403 response details", async () => {
    await expect(interceptorErrorHandler(make403OrgSetupError(5))).rejects.toThrow()

    expect(mockSetTenant).toHaveBeenCalledOnce()
    const payload = mockSetTenant.mock.calls[0][0] as Record<string, unknown>
    expect(payload.org_setup_step).toBe(5)
  })

  it("handles null workspaceStore.entityId gracefully (no entity selected yet)", async () => {
    ;(useWorkspaceStore.getState as Mock).mockReturnValue({
      entityId: null,
      orgId: "org-001",
    })

    await expect(interceptorErrorHandler(make403OrgSetupError(1))).rejects.toThrow()

    expect(mockSetTenant).toHaveBeenCalledOnce()
    const payload = mockSetTenant.mock.calls[0][0] as Record<string, unknown>
    expect(payload.active_entity_id).toBeNull()
  })
})
