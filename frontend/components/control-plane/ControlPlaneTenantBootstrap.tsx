"use client"

import { useEffect } from "react"
import type { EntityRole } from "@/types/api"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"

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
  const { setOrgId, setEntityId } = useWorkspaceStore()

  useEffect(() => {
    setTenant({
      tenant_id: tenantId,
      tenant_slug: tenantSlug,
      org_setup_complete: orgSetupComplete,
      org_setup_step: orgSetupStep,
      entity_roles: entityRoles,
    })
    setOrgId(tenantId)
    setEntityId(entityRoles.at(0)?.entity_id ?? null)
  }, [entityRoles, orgSetupComplete, orgSetupStep, setEntityId, setOrgId, setTenant, tenantId, tenantSlug])

  return null
}
