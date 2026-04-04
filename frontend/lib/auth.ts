import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { CredentialsSignin } from "next-auth"
import type { EntityRole } from "@/types/api"

export type UserRole =
  | "super_admin"
  | "platform_owner"
  | "platform_admin"
  | "platform_support"
  | "finance_leader"
  | "finance_team"
  | "director"
  | "entity_user"
  | "auditor"
  | "hr_manager"
  | "employee"
  | "read_only"

const getApiBaseUrl = (): string => {
  const base = process.env.NEXT_PUBLIC_API_URL?.trim()
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_URL environment variable is required at runtime.")
  }
  return base.replace(/\/+$/, "")
}

interface BackendEnvelope<T> {
  data: T | null
  error: {
    code: string
    message: string
    details?: unknown
  } | null
}

interface LoginTokenPayload {
  access_token: string
  refresh_token: string
  token_type: string
}

interface LoginChallengePayload {
  requires_mfa: true
  mfa_challenge_token: string
}

type LoginPayload = LoginTokenPayload | LoginChallengePayload

interface MePayload {
  user_id: string
  email: string
  full_name: string
  role: UserRole
  tenant: {
    tenant_id: string
    display_name: string
    slug?: string
    org_setup_complete?: boolean
    org_setup_step?: number
  }
}

class MFARequiredError extends CredentialsSignin {
  code = "mfa_required"
}

const parseJwtExpMs = (token: string): number => {
  try {
    const payload = JSON.parse(atob(token.split(".")[1] ?? ""))
    if (typeof payload.exp === "number") {
      return payload.exp * 1000
    }
  } catch {
    // Intentionally ignore parse failures and use a safe default.
  }
  return Date.now() + 15 * 60 * 1000
}

const normalizeTenantSlug = (displayName: string): string =>
  displayName
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "dev"

const fetchEnvelope = async <T>(
  path: string,
  init: RequestInit,
): Promise<BackendEnvelope<T>> => {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  })

  const payload = (await response.json()) as BackendEnvelope<T> | T
  if (
    typeof payload === "object" &&
    payload !== null &&
    "data" in payload &&
    "error" in payload
  ) {
    return payload as BackendEnvelope<T>
  }
  if (response.ok) {
    return { data: payload as T, error: null }
  }
  return {
    data: null,
    error: {
      code: "http_error",
      message: response.statusText,
    },
  }
}

const refreshAccessToken = async (token: {
  refresh_token: string
  access_token: string
  access_token_expires_at: number
}) => {
  try {
    const envelope = await fetchEnvelope<LoginTokenPayload>("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({
        refresh_token: token.refresh_token,
      }),
    })

    if (!envelope.data || envelope.error) {
      throw new Error(envelope.error?.message ?? "Unable to refresh token")
    }

    return {
      ...token,
      access_token: envelope.data.access_token,
      refresh_token: envelope.data.refresh_token,
      access_token_expires_at: parseJwtExpMs(envelope.data.access_token),
    }
  } catch {
    return {
      ...token,
      error: "RefreshAccessTokenError" as const,
    }
  }
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        totp_code: { label: "TOTP Code", type: "text" },
        mfa_challenge_token: { label: "MFA Challenge Token", type: "text" },
        access_token: { label: "Access Token", type: "text" },
        refresh_token: { label: "Refresh Token", type: "text" },
      },
      async authorize(credentials) {
        const email = typeof credentials?.email === "string" ? credentials.email : undefined
        const password = typeof credentials?.password === "string" ? credentials.password : undefined
        const totpCode = typeof credentials?.totp_code === "string" ? credentials.totp_code : undefined
        const mfaChallengeToken =
          typeof credentials?.mfa_challenge_token === "string"
            ? credentials.mfa_challenge_token
            : undefined
        const accessToken =
          typeof credentials?.access_token === "string" ? credentials.access_token : undefined
        const refreshToken =
          typeof credentials?.refresh_token === "string" ? credentials.refresh_token : undefined

        let tokenPayload: LoginTokenPayload | null = null

        if (accessToken && refreshToken) {
          tokenPayload = {
            access_token: accessToken,
            refresh_token: refreshToken,
            token_type: "bearer",
          }
        } else if (mfaChallengeToken) {
          if (!totpCode) {
            return null
          }
          const mfaEnvelope = await fetchEnvelope<LoginPayload>(
            "/api/v1/auth/mfa/verify",
            {
              method: "POST",
              body: JSON.stringify({
                mfa_challenge_token: mfaChallengeToken,
                totp_code: totpCode,
              }),
            },
          )
          if (!mfaEnvelope.data || mfaEnvelope.error) {
            return null
          }
          if (!("access_token" in mfaEnvelope.data)) {
            return null
          }
          tokenPayload = mfaEnvelope.data
        } else {
          if (!email || !password) {
            return null
          }
          const loginEnvelope = await fetchEnvelope<LoginPayload>(
            "/api/v1/auth/login",
            {
              method: "POST",
              body: JSON.stringify({
                email,
                password,
              }),
            },
          )

          if (!loginEnvelope.data || loginEnvelope.error) {
            const message = loginEnvelope.error?.message ?? "Invalid credentials"
            if (message.toLowerCase().includes("totp code required")) {
              throw new MFARequiredError()
            }
            return null
          }
          if ("requires_mfa" in loginEnvelope.data && loginEnvelope.data.requires_mfa) {
            throw new MFARequiredError()
          }
          if (!("access_token" in loginEnvelope.data)) {
            return null
          }
          tokenPayload = loginEnvelope.data
        }

        if (
          !tokenPayload ||
          !tokenPayload.access_token ||
          !tokenPayload.refresh_token
        ) {
          return null
        }

        const meEnvelope = await fetchEnvelope<MePayload>("/api/v1/auth/me", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${tokenPayload.access_token}`,
          },
        })

        if (!meEnvelope.data || meEnvelope.error) {
          return null
        }

        const entityRoles: EntityRole[] = []
        return {
          id: meEnvelope.data.user_id,
          email: meEnvelope.data.email,
          name: meEnvelope.data.full_name,
          role: meEnvelope.data.role,
          tenant_id: meEnvelope.data.tenant.tenant_id,
          tenant_slug:
            meEnvelope.data.tenant.slug && meEnvelope.data.tenant.slug.trim()
              ? meEnvelope.data.tenant.slug
              : normalizeTenantSlug(meEnvelope.data.tenant.display_name),
          org_setup_complete: Boolean(meEnvelope.data.tenant.org_setup_complete),
          org_setup_step:
            typeof meEnvelope.data.tenant.org_setup_step === "number"
              ? meEnvelope.data.tenant.org_setup_step
              : 0,
          entity_roles: entityRoles,
          access_token: tokenPayload.access_token,
          refresh_token: tokenPayload.refresh_token,
          access_token_expires_at: parseJwtExpMs(tokenPayload.access_token),
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        return {
          ...token,
          sub: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
          tenant_id: user.tenant_id,
          tenant_slug: user.tenant_slug,
          org_setup_complete: user.org_setup_complete,
          org_setup_step: user.org_setup_step,
          entity_roles: user.entity_roles,
          access_token: user.access_token,
          refresh_token: user.refresh_token,
          access_token_expires_at: user.access_token_expires_at,
        }
      }

      if (Date.now() < (token.access_token_expires_at ?? 0)) {
        return token
      }

      return refreshAccessToken({
        refresh_token: token.refresh_token,
        access_token: token.access_token,
        access_token_expires_at: token.access_token_expires_at,
      }).then((refreshed) => ({
        ...token,
        ...refreshed,
      }))
    },
    async session({ session, token }) {
      session.user = {
        ...session.user,
        id: token.sub,
        email: token.email,
        name: token.name,
        role: token.role,
        tenant_id: token.tenant_id,
        tenant_slug: token.tenant_slug,
        org_setup_complete: token.org_setup_complete,
        org_setup_step: token.org_setup_step,
        entity_roles: token.entity_roles ?? [],
      }
      session.access_token = token.access_token
      session.refresh_token = token.refresh_token
      session.access_token_expires_at = token.access_token_expires_at
      return session
    },
  },
  pages: {
    signIn: "/login",
  },
  trustHost: true,
  session: {
    strategy: "jwt",
  },
})
