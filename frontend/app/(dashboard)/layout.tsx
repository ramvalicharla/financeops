import type { ReactNode } from "react"
import { headers } from "next/headers"
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import type { UserRole } from "@/lib/auth"
import { DataActivationReminder } from "@/components/layout/DataActivationReminder"
import { ContextBar } from "@/components/layout/ContextBar"
import { Sidebar } from "@/components/layout/Sidebar"
import { DisplayPreferenceBootstrap } from "@/components/layout/DisplayPreferenceBootstrap"
import { ModuleTabs } from "@/components/layout/ModuleTabs"
import { Topbar } from "@/components/layout/Topbar"
import { IntentPanel } from "@/components/panels/IntentPanel"
import { JobPanel } from "@/components/panels/JobPanel"
import { TimelinePanel } from "@/components/panels/TimelinePanel"
import { DeterminismPanel } from "@/components/panels/DeterminismPanel"
import { SearchProvider } from "@/components/search/SearchProvider"
import { Breadcrumb } from "@/components/ui/Breadcrumb"
import { DashboardShell } from "@/components/layout/DashboardShell"
import { CommandPalette } from "@/components/layout/_components/CommandPalette"

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode
}) {
  const requestHeaders = headers()
  const isE2EBypass = process.env.NODE_ENV !== "production"
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
  const userRole = user.role as UserRole

  const tenantSlugHeader = requestHeaders.get("x-tenant-slug")
  const tenantSlug = tenantSlugHeader || user.tenant_slug || "dev"

  return (
    <div className="h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,hsl(var(--brand-primary)/0.08),transparent_28%),hsl(var(--background))] text-foreground">
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
      <DashboardShell>
        <SearchProvider>
          <DisplayPreferenceBootstrap />
          <Topbar
            entityRoles={user.entity_roles}
            tenantSlug={tenantSlug}
            userEmail={user.email ?? ""}
            userName={user.name ?? "Finance User"}
          />
          <ModuleTabs />
          <ContextBar tenantSlug={tenantSlug} />
          <main id="main-content" className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
            <DataActivationReminder
              initialCoaStatus={user.coa_status}
              initialOnboardingScore={user.onboarding_score}
            />
            <div className="px-4 pt-3 pb-0 md:px-6">
              <Breadcrumb />
            </div>
            <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">
              {children}
            </div>
          </main>
          <IntentPanel />
          <JobPanel />
          <TimelinePanel />
          <DeterminismPanel />
          <CommandPalette />
        </SearchProvider>
      </DashboardShell>
    </div>
  )
}
