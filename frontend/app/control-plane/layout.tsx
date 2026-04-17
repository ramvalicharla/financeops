import type { ReactNode } from "react"
import { headers } from "next/headers"
import { redirect } from "next/navigation"
import { ControlPlaneShell } from "@/components/control-plane/ControlPlaneShell"
import { auth } from "@/lib/auth"
import type { UserRole } from "@/lib/auth"

export default async function ControlPlaneLayout({
  children,
}: {
  children: ReactNode
}) {
  const requestHeaders = await headers()
  const isE2EBypass =
    process.env.NODE_ENV !== "production" &&
    requestHeaders.get("x-e2e-auth-bypass") === "true"
  const session = await auth()
  if (!session?.user && !isE2EBypass) {
    redirect("/login")
  }

  const fallbackUser = isE2EBypass
    ? {
        id: "user-001",
        name: "Test User",
        email: "test@acme.com",
        role: "finance_leader",
        tenant_id: "tenant-001",
        tenant_slug: "acme",
        org_setup_complete: true,
        org_setup_step: 7,
        coa_status: "uploaded" as const,
        onboarding_score: 100,
        entity_roles: [
          { entity_id: "entity-001", entity_name: "Acme Ltd", role: "admin" as const },
          {
            entity_id: "entity-002",
            entity_name: "Acme Holdings",
            role: "accountant" as const,
          },
        ],
      }
    : null
  const user = session?.user ?? fallbackUser
  if (!user) {
    redirect("/login")
  }

  const role = String(user.role ?? "")
  if (
    !isE2EBypass &&
    !["platform_owner", "platform_admin", "super_admin", "admin"].includes(role)
  ) {
    redirect("/dashboard")
  }

  const tenantSlugHeader = requestHeaders.get("x-tenant-slug")
  const tenantSlug = tenantSlugHeader || user.tenant_slug || "dev"

  return (
    <ControlPlaneShell
      tenantId={user.tenant_id}
      tenantSlug={tenantSlug}
      userName={user.name ?? "Finance User"}
      userEmail={user.email ?? ""}
      userRole={user.role as UserRole}
      orgSetupComplete={user.org_setup_complete}
      orgSetupStep={user.org_setup_step}
      entityRoles={user.entity_roles}
    >
      {children}
    </ControlPlaneShell>
  )
}
