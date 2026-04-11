"use client"

import { useEffect } from "react"
import type { EntityRole } from "@/types/api"
import { useTenantStore } from "@/lib/store/tenant"

interface ControlPlaneTenantBootstrapProps {
  tenantId: string
  tenantSlug: string
  orgSetupComplete: boolean
  orgSetupStep: number
  entityRoles: EntityRole[]
}

export function ControlPlaneTenantBootstrap({
  tenantId,
  tenantSlug,
  orgSetupComplete,
  orgSetupStep,
  entityRoles,
}: ControlPlaneTenantBootstrapProps) {
  const setTenant = useTenantStore((state) => state.setTenant)

  useEffect(() => {
    setTenant({
      tenant_id: tenantId,
      tenant_slug: tenantSlug,
      org_setup_complete: orgSetupComplete,
      org_setup_step: orgSetupStep,
      entity_roles: entityRoles,
      active_entity_id: entityRoles.at(0)?.entity_id ?? null,
    })
  }, [entityRoles, orgSetupComplete, orgSetupStep, setTenant, tenantId, tenantSlug])

  return null
}
