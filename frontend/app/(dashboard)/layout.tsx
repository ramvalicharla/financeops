import type { ReactNode } from "react"
import { headers } from "next/headers"
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import type { UserRole } from "@/lib/auth"
import { Sidebar } from "@/components/layout/Sidebar"
import { DisplayPreferenceBootstrap } from "@/components/layout/DisplayPreferenceBootstrap"
import { Topbar } from "@/components/layout/Topbar"
import { SearchProvider } from "@/components/search/SearchProvider"

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode
}) {
  const requestHeaders = headers()
  const isE2EBypass =
    process.env.NODE_ENV !== "production" &&
    requestHeaders.get("x-e2e-auth-bypass") === "true"
  const session = await auth()
  if (!session?.user && !isE2EBypass) {
    redirect("/login")
  }

  const fallbackUser = {
    id: "user-001",
    name: "Test User",
    email: "test@acme.com",
    role: "finance_leader",
    tenant_id: "tenant-001",
    tenant_slug: "acme",
    org_setup_complete: true,
    org_setup_step: 7,
    entity_roles: [
      { entity_id: "entity-001", entity_name: "Acme Ltd", role: "admin" as const },
      {
        entity_id: "entity-002",
        entity_name: "Acme Holdings",
        role: "accountant" as const,
      },
    ],
  }
  const user = session?.user ?? fallbackUser
  const userRole = user.role as UserRole

  const tenantSlugHeader = requestHeaders.get("x-tenant-slug")
  const tenantSlug = tenantSlugHeader || user.tenant_slug || "dev"

  return (
    <div className="h-screen overflow-hidden bg-background text-foreground">
      <Sidebar
        entityRoles={user.entity_roles}
        userRole={userRole}
        tenantId={user.tenant_id}
        tenantSlug={tenantSlug}
        orgSetupComplete={user.org_setup_complete}
        orgSetupStep={user.org_setup_step}
        userEmail={user.email ?? ""}
        userName={user.name ?? "Finance User"}
      />
      <div className="flex h-full flex-col md:pl-60">
        <SearchProvider>
          <DisplayPreferenceBootstrap />
          <Topbar
            entityRoles={user.entity_roles}
            tenantSlug={tenantSlug}
            userEmail={user.email ?? ""}
            userName={user.name ?? "Finance User"}
          />
          <main id="main-content" className="flex-1 overflow-y-auto p-6">{children}</main>
        </SearchProvider>
      </div>
    </div>
  )
}
