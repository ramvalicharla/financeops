import type { DefaultSession } from "next-auth"
import type { CoaStatus, EntityRole } from "@/types/api"
import type { UserRole } from "@/lib/auth"

declare module "next-auth" {
  interface Session {
    accessToken: string
    access_token: string
    refresh_token: string
    access_token_expires_at: number
    user: DefaultSession["user"] & {
      id: string
      role: UserRole
      tenant_id: string
      tenant_slug: string
      org_setup_complete: boolean
      org_setup_step: number
      coa_status: CoaStatus
      onboarding_score: number
      entity_roles: EntityRole[]
    }
  }

  interface User {
    id: string
    email: string
    name: string
    role: UserRole
    tenant_id: string
    tenant_slug: string
    org_setup_complete: boolean
    org_setup_step: number
    coa_status: CoaStatus
    onboarding_score: number
    entity_roles: EntityRole[]
    accessToken: string
    access_token: string
    refresh_token: string
    access_token_expires_at: number
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    sub: string
    email: string
    name: string
    role: UserRole
    tenant_id: string
    tenant_slug: string
    org_setup_complete: boolean
    org_setup_step: number
    coa_status: CoaStatus
    onboarding_score: number
    entity_roles: EntityRole[]
    accessToken: string
    access_token: string
    refresh_token: string
    access_token_expires_at: number
    error?: "RefreshAccessTokenError"
  }
}
