"use client"

import type { ReactNode } from "react"
import type { EntityRole } from "@/types/api"
import type { UserRole } from "@/lib/auth"
import { DisplayPreferenceBootstrap } from "@/components/layout/DisplayPreferenceBootstrap"
import { SearchProvider } from "@/components/search/SearchProvider"
import { DeterminismPanel } from "@/components/panels/DeterminismPanel"
import { IntentPanel } from "@/components/panels/IntentPanel"
import { JobPanel } from "@/components/panels/JobPanel"
import { TimelinePanel } from "@/components/panels/TimelinePanel"
import { ActivityTray } from "@/components/control-plane/ActivityTray"
import { AppSidebar } from "@/components/control-plane/AppSidebar"
import { ContextHeader } from "@/components/control-plane/ContextHeader"
import { ControlPlaneTenantBootstrap } from "@/components/control-plane/ControlPlaneTenantBootstrap"
import { EvidenceDrawer } from "@/components/control-plane/EvidenceDrawer"
import { TopCommandBar } from "@/components/control-plane/TopCommandBar"

interface ControlPlaneShellProps {
  children: ReactNode
  tenantSlug: string
  tenantId: string
  userName: string
  userEmail: string
  userRole: UserRole
  orgSetupComplete: boolean
  orgSetupStep: number
  entityRoles: EntityRole[]
}

export function ControlPlaneShell({
  children,
  tenantSlug,
  tenantId,
  userName,
  userEmail,
  userRole,
  orgSetupComplete,
  orgSetupStep,
  entityRoles,
}: ControlPlaneShellProps) {
  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,hsl(var(--brand-primary)/0.08),transparent_28%),hsl(var(--background))] text-foreground">
      <SearchProvider>
        <DisplayPreferenceBootstrap />
        <ControlPlaneTenantBootstrap
          tenantId={tenantId}
          tenantSlug={tenantSlug}
          orgSetupComplete={orgSetupComplete}
          orgSetupStep={orgSetupStep}
          entityRoles={entityRoles}
        />
        <AppSidebar
          tenantSlug={tenantSlug}
          userRole={userRole}
          userName={userName}
          userEmail={userEmail}
          entityRoles={entityRoles}
        />
        <div className="flex min-h-screen flex-col md:pl-64">
          <TopCommandBar userName={userName} userEmail={userEmail} userRole={userRole} />
          <ContextHeader tenantSlug={tenantSlug} userRole={userRole} />
          <main id="main-content" className="flex-1 overflow-y-auto px-4 py-6 pb-24 md:px-6">
            <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">{children}</div>
          </main>
          <ActivityTray />
          <EvidenceDrawer />
          <IntentPanel />
          <JobPanel />
          <TimelinePanel />
          <DeterminismPanel />
        </div>
      </SearchProvider>
    </div>
  )
}
