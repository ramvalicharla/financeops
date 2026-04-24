"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"
import type { EntityRole } from "@/types/api"

interface TenantState {
  // ── real session state (persisted) ───────────────────────────────────────
  tenant_id: string | null
  tenant_slug: string | null
  org_setup_complete: boolean
  org_setup_step: number
  active_entity_id: string | null
  entity_roles: EntityRole[]

  // ── org-switch state (NOT persisted — switch token is short-lived) ────────
  is_switched: boolean
  switch_token: string | null
  switched_tenant_id: string | null
  switched_tenant_name: string | null
  switched_tenant_slug: string | null

  // ── actions ───────────────────────────────────────────────────────────────
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

  /** Platform owner enters a switched-tenant view. */
  enterSwitchMode: (params: {
    switch_token: string
    tenant_id: string
    tenant_name: string
    tenant_slug?: string
  }) => void
  /** Restore the original session — clears all switch state. */
  exitSwitchMode: () => void
}

const initialState = {
  tenant_id: null,
  tenant_slug: null,
  org_setup_complete: false,
  org_setup_step: 0,
  active_entity_id: null,
  entity_roles: [] as EntityRole[],
  // switch state
  is_switched: false,
  switch_token: null,
  switched_tenant_id: null,
  switched_tenant_name: null,
  switched_tenant_slug: null,
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
          // always clear switch state when the real tenant is set
          is_switched: false,
          switch_token: null,
          switched_tenant_id: null,
          switched_tenant_name: null,
          switched_tenant_slug: null,
        }),

      setActiveEntity: (entityId) => set({ active_entity_id: entityId }),

      clearTenant: () => set(initialState),

      enterSwitchMode: ({ switch_token, tenant_id, tenant_name, tenant_slug }) =>
        set({
          is_switched: true,
          switch_token,
          switched_tenant_id: tenant_id,
          switched_tenant_name: tenant_name,
          switched_tenant_slug: tenant_slug ?? null,
        }),

      exitSwitchMode: () =>
        set({
          is_switched: false,
          switch_token: null,
          switched_tenant_id: null,
          switched_tenant_name: null,
          switched_tenant_slug: null,
        }),
    }),
    {
      name: "financeops-tenant-store",
      storage: createJSONStorage(() => sessionStorage),
      // Switch-mode fields are intentionally excluded — a switch token is
      // short-lived (15 min) and must not survive a page reload.
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
