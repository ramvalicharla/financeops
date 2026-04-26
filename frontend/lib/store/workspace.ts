"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface WorkspaceState {
  // Workspace context — what the user is currently viewing
  orgId: string | null // Current workspace org. NOT the user's identity org.
  entityId: string | null // Current entity drill-down, null = all entities in org
  entityCurrency: string | null // Functional currency of current entity, null = all-entities view
  moduleId: string | null // Currently-open module tab
  period: string | null // Active period (fiscal year + period code, e.g. "FY26-Q1")

  // UI preferences
  sidebarCollapsed: boolean

  // Actions
  setOrgId: (orgId: string | null) => void
  setEntityId: (entityId: string | null) => void
  setModuleId: (moduleId: string | null) => void
  setPeriod: (period: string | null) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void

  // Cross-cutting action: entity change resets module if needed
  switchEntity: (entityId: string | null) => void

  // Cross-cutting action: org change resets everything downstream
  switchOrg: (orgId: string | null) => void
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      orgId: null,
      entityId: null,
      entityCurrency: null,
      moduleId: null,
      period: null,
      sidebarCollapsed: false,

      setOrgId: (orgId) => set({ orgId }),
      setEntityId: (entityId) => set({ entityId }),
      setModuleId: (moduleId) => set({ moduleId }),
      setPeriod: (period) => set({ period }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),

      switchEntity: (entityId) => {
        // Entity change preserves module, period, sidebar state
        set({ entityId })
      },

      switchOrg: (orgId) => {
        // Org change resets all downstream workspace context
        set({
          orgId,
          entityId: null,
          entityCurrency: null,
          moduleId: null,
          // period: keep current period selection across org switches
        })
      },
    }),
    {
      name: "finqor-workspace",
      // Persist everything except moduleId — module tab should restore to
      // Overview (or module list default) on a fresh session.
      partialize: (state) => ({
        orgId: state.orgId,
        entityId: state.entityId,
        period: state.period,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
      onRehydrateStorage: () => (state) => {
        // One-time migration: hydrate from pre-Phase-0 legacy store keys.
        // Runs after Zustand rehydrates — only migrates if the new store is empty.
        if (typeof window === "undefined" || !state) return
        try {
          if (!state.entityId && !state.orgId) {
            const rawTenant = sessionStorage.getItem("financeops-tenant-store")
            if (rawTenant) {
              const parsed = JSON.parse(rawTenant) as {
                state?: { tenant_id?: string; active_entity_id?: string }
              }
              const legacy = parsed.state ?? {}
              if (legacy.tenant_id)
                useWorkspaceStore.setState({ orgId: legacy.tenant_id })
              if (legacy.active_entity_id)
                useWorkspaceStore.setState({ entityId: legacy.active_entity_id })
            }
          }
        } catch (e) {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[workspaceStore] legacy migration failed:", e)
          }
        }
        try {
          if (!state.period) {
            const rawUI = localStorage.getItem("financeops-ui-store")
            if (rawUI) {
              const parsed = JSON.parse(rawUI) as {
                state?: { activePeriod?: string; sidebarCollapsed?: boolean }
              }
              const legacy = parsed.state ?? {}
              if (legacy.activePeriod)
                useWorkspaceStore.setState({ period: legacy.activePeriod })
              if (legacy.sidebarCollapsed !== undefined)
                useWorkspaceStore.setState({
                  sidebarCollapsed: legacy.sidebarCollapsed,
                })
            }
          }
        } catch (e) {
          if (process.env.NODE_ENV !== "production") {
            console.warn("[workspaceStore] legacy UI migration failed:", e)
          }
        }
      },
    },
  ),
)
