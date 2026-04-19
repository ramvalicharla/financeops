"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

interface UIState {
  sidebarOpen: boolean
  sidebarCollapsed: boolean
  density: "comfortable" | "compact"
  activePeriod: string
  notificationCount: number
  notificationItems: Array<{
    id: string
    label: string
    href: string
  }>
  billingWarning: string | null
  billingWarningDismissed: boolean
  pinnedModules: string[]
  recentSearches: string[]
  toggleSidebar: () => void
  closeSidebar: () => void
  toggleSidebarCollapsed: () => void
  setDensity: (density: "comfortable" | "compact") => void
  setActivePeriod: (period: string) => void
  setNotificationCount: (count: number) => void
  setNotificationItems: (
    items: Array<{
      id: string
      label: string
      href: string
    }>,
  ) => void
  setBillingWarning: (warning: string | null) => void
  dismissBillingWarning: () => void
  togglePinModule: (href: string) => void
  addRecentSearch: (query: string) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      sidebarCollapsed: false,
      density: "comfortable",
      activePeriod: new Date().toISOString().slice(0, 7),
      notificationCount: 0,
      notificationItems: [],
      billingWarning: null,
      billingWarningDismissed: false,
      pinnedModules: [],
      recentSearches: [],
      toggleSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      closeSidebar: () => set({ sidebarOpen: false }),
      toggleSidebarCollapsed: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setDensity: (density) => set({ density }),
      setActivePeriod: (period) => set({ activePeriod: period }),
      setNotificationCount: (count) => set({ notificationCount: count }),
      setNotificationItems: (items) =>
        set({ notificationItems: items, notificationCount: items.length }),
      setBillingWarning: (warning) =>
        set({
          billingWarning: warning,
          billingWarningDismissed: warning ? false : true,
        }),
      dismissBillingWarning: () => set({ billingWarningDismissed: true }),
      togglePinModule: (href) => set((state) => ({
        pinnedModules: state.pinnedModules.includes(href) 
          ? state.pinnedModules.filter((p) => p !== href) 
          : [...state.pinnedModules, href]
      })),
      addRecentSearch: (query) => set((state) => {
        const lower = query.trim().toLowerCase()
        if (!lower) return {}
        const filtered = state.recentSearches.filter(s => s !== lower)
        return { recentSearches: [lower, ...filtered].slice(0, 10) }
      }),
    }),
    {
      name: "financeops-ui-store",
      // localStorage so sidebarCollapsed survives page refresh.
      // (Previously sessionStorage — only sidebarCollapsed requires cross-session
      // persistence, but a single persist layer only supports one storage.)
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        sidebarCollapsed: state.sidebarCollapsed,
        density: state.density,
        activePeriod: state.activePeriod,
        notificationCount: state.notificationCount,
        notificationItems: state.notificationItems,
        billingWarning: state.billingWarning,
        billingWarningDismissed: state.billingWarningDismissed,
        pinnedModules: state.pinnedModules,
        recentSearches: state.recentSearches,
      }),
    },
  ),
)
