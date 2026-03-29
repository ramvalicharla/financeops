"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"
import type { EntityRole } from "@/types/api"

interface TenantState {
  tenant_id: string | null
  tenant_slug: string | null
  org_setup_complete: boolean
  org_setup_step: number
  active_entity_id: string | null
  entity_roles: EntityRole[]
  setTenant: (payload: {
    tenant_id: string
    tenant_slug: string
    org_setup_complete?: boolean
    org_setup_step?: number
    entity_roles: EntityRole[]
    active_entity_id?: string | null
  }) => void
  setActiveEntity: (entityId: string | null) => void
  clearTenant: () => void
}

const initialState = {
  tenant_id: null,
  tenant_slug: null,
  org_setup_complete: false,
  org_setup_step: 0,
  active_entity_id: null,
  entity_roles: [] as EntityRole[],
}

export const useTenantStore = create<TenantState>()(
  persist(
    (set) => ({
      ...initialState,
      setTenant: ({
        tenant_id,
        tenant_slug,
        org_setup_complete,
        org_setup_step,
        entity_roles,
        active_entity_id,
      }) =>
        set({
          tenant_id,
          tenant_slug,
          org_setup_complete: org_setup_complete ?? false,
          org_setup_step: org_setup_step ?? 0,
          entity_roles,
          active_entity_id:
            active_entity_id ?? entity_roles.at(0)?.entity_id ?? null,
        }),
      setActiveEntity: (entityId) => set({ active_entity_id: entityId }),
      clearTenant: () => set(initialState),
    }),
    {
      name: "financeops-tenant-store",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        tenant_id: state.tenant_id,
        tenant_slug: state.tenant_slug,
        org_setup_complete: state.org_setup_complete,
        org_setup_step: state.org_setup_step,
        active_entity_id: state.active_entity_id,
        entity_roles: state.entity_roles,
      }),
    },
  ),
)
