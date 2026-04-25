"use client"

import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { signOut } from "next-auth/react"
import * as Sentry from "@sentry/browser"
import { ZodError, type ZodType } from "zod"
import { useTenantStore } from "@/lib/store/tenant"
import { useLocationStore } from "@/lib/store/location"
import { useUIStore } from "@/lib/store/ui"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { shouldSignOutOnUnauthorized } from "@/lib/api/auth-unauthorized"
import { consumeAuthRecoveryAttempt } from "@/lib/api/auth-loop-guard"
import { readSessionForApi } from "@/lib/api/session-cache"
import type { ApiResponse } from "@/types/api"

type ApiErrorPayload = {
  code: string
  message: string
  details?: unknown
}

type ApiClientError = Error & {
  payload?: ApiErrorPayload
  details?: unknown
  response?: {
    status?: number
  }
}

type SessionTokenCarrier = {
  access_token?: unknown
  accessToken?: unknown
} | null | undefined

export class ApiValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = "ApiValidationError"
  }
}

const createApiClientError = (
  message: string,
  status?: number,
  payload?: ApiErrorPayload,
): ApiClientError => {
  const error = new Error(message) as ApiClientError
  if (status) {
    error.response = { status }
  }
  if (payload) {
    error.payload = payload
    error.details = payload.details
  }
  return error
}

export const parseWithSchema = <T>(
  endpoint: string,
  raw: unknown,
  schema: ZodType<T>,
): T => {
  try {
    return schema.parse(raw)
  } catch (error) {
    if (error instanceof ZodError) {
      Sentry.captureException(error, {
        extra: {
          endpoint,
          firstIssuePath: error.issues[0]?.path,
          firstIssueMessage: error.issues[0]?.message,
        },
      })
      throw new ApiValidationError(
        "Received unexpected data from server. Our team has been notified.",
      )
    }
    throw error
  }
}

export const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").trim()

export const readAccessTokenFromSession = (session: SessionTokenCarrier): string => {
  if (typeof session?.access_token === "string" && session.access_token) {
    return session.access_token
  }
  if (typeof session?.accessToken === "string" && session.accessToken) {
    return session.accessToken
  }
  return ""
}

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
})

const captureBillingWarning = (warningHeader?: string) => {
  if (!warningHeader) {
    return
  }
  useUIStore.getState().setBillingWarning(warningHeader)
}

export const setAuthHeaders = async (config: InternalAxiosRequestConfig) => {
  if (!BASE_URL) {
    throw new Error("NEXT_PUBLIC_API_URL is required")
  }
  const session = await readSessionForApi()
  const sessionToken = readAccessTokenFromSession(session)
  const state = useTenantStore.getState()
  const workspaceState = useWorkspaceStore.getState()
  const locationState = useLocationStore.getState()

  config.headers.set("X-Request-ID", crypto.randomUUID())

  // When in org-switch mode, use the short-lived switch_token as the Bearer
  // and target the switched tenant's ID instead of the real one.
  const isSwitched = state.is_switched && Boolean(state.switch_token)
  const bearerToken = isSwitched ? (state.switch_token ?? sessionToken) : sessionToken
  const effectiveTenantId = isSwitched ? (state.switched_tenant_id ?? state.tenant_id) : state.tenant_id

  if (bearerToken) {
    config.headers.set("Authorization", `Bearer ${bearerToken}`)
  }
  if (effectiveTenantId) {
    config.headers.set("X-Tenant-ID", effectiveTenantId)
  }
  if (workspaceState.entityId) {
    config.headers.set("X-Entity-ID", workspaceState.entityId)
  }
  if (locationState.active_location_id) {
    config.headers.set("X-Location-ID", locationState.active_location_id)
  }

  const method = config.method?.toUpperCase()
  if (
    method &&
    ["POST", "PUT", "PATCH"].includes(method) &&
    !config.headers.has("Idempotency-Key")
  ) {
    config.headers.set("Idempotency-Key", crypto.randomUUID())
  }
}

apiClient.interceptors.request.use(async (config) => {
  await setAuthHeaders(config)
  return config
})

apiClient.interceptors.response.use(
  (response) => {
    captureBillingWarning(response.headers["x-billing-warning"])
    if (
      response.config.responseType === "blob" ||
      response.config.responseType === "arraybuffer"
    ) {
      return response
    }
    const payload = response.data as ApiResponse<unknown>
    const isEnvelope =
      payload !== null &&
      typeof payload === "object" &&
      ("data" in payload || "error" in payload || "meta" in payload)
    if (isEnvelope && payload.error) {
      const err = new Error(payload.error.message) as Error & {
        payload?: ApiErrorPayload
      }
      err.payload = payload.error
      throw err
    }
    if (isEnvelope) {
      response.data = payload.data
    }
    return response
  },
  async (error: AxiosError<ApiResponse<unknown>>) => {
    captureBillingWarning(error.response?.headers?.["x-billing-warning"] as string | undefined)
    const status = error.response?.status
    const envelopeError = error.response?.data?.error

    // If a 401 arrives while in org-switch mode, the switch token has expired.
    // Exit switch mode and return to the real session rather than signing out.
    if (status === 401 && useTenantStore.getState().is_switched) {
      useTenantStore.getState().exitSwitchMode()
      if (typeof window !== "undefined") {
        window.location.assign("/dashboard?switch_expired=1")
      }
      return Promise.reject(error)
    }

    if (shouldSignOutOnUnauthorized(error, BASE_URL)) {
      const requestPath = error.config?.url ?? ""
      if (consumeAuthRecoveryAttempt("sign_out", requestPath)) {
        await signOut({ callbackUrl: "/login" })
      }
      return Promise.reject(error)
    }

    if (status === 402) {
      if (typeof window !== "undefined") {
        window.location.assign("/billing?reason=suspended")
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      if (envelopeError?.code === "ORG_SETUP_REQUIRED") {
        const details =
          envelopeError.details && typeof envelopeError.details === "object"
            ? (envelopeError.details as { current_step?: unknown })
            : undefined
        const currentStep =
          typeof details?.current_step === "number" ? details.current_step : 0
        const tenantState = useTenantStore.getState()
        if (tenantState.tenant_id && tenantState.tenant_slug) {
          tenantState.setTenant({
            tenant_id: tenantState.tenant_id,
            tenant_slug: tenantState.tenant_slug,
            org_setup_complete: false,
            org_setup_step: currentStep || tenantState.org_setup_step,
            entity_roles: tenantState.entity_roles,
            active_entity_id: tenantState.active_entity_id,
          })
        }
        if (typeof window !== "undefined") {
          const nextPath = `${window.location.pathname}${window.location.search}`
          if (consumeAuthRecoveryAttempt("org_setup_redirect", nextPath)) {
            window.location.assign(`/org-setup?next=${encodeURIComponent(nextPath)}`)
          }
        }
        return Promise.reject(new Error("ORG_SETUP_REQUIRED"))
      }
      return Promise.reject(
        createApiClientError(
          envelopeError?.message ?? "Permission denied",
          status,
          envelopeError ?? undefined,
        ),
      )
    }

    if (status === 422) {
      const validationError = createApiClientError(
        envelopeError?.message ?? "Validation error",
        status,
        envelopeError ?? undefined,
      )
      return Promise.reject(validationError)
    }

    if (status && status >= 500) {
      return Promise.reject(
        createApiClientError(
          "Server error, please try again",
          status,
          envelopeError ?? undefined,
        ),
      )
    }

    if (envelopeError?.message) {
      return Promise.reject(
        createApiClientError(envelopeError.message, status, envelopeError),
      )
    }

    return Promise.reject(error)
  },
)

export default apiClient
