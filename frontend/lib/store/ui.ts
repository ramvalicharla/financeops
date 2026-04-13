"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

interface UIState {
  sidebarOpen: boolean
  sidebarCollapsed: boolean
  activePeriod: string
  notificationCount: number
  notificationItems: Array<{
    id: string
    label: string
    href: string
  }>
  billingWarning: string | null
  billingWarningDismissed: boolean
  toggleSidebar: () => void
  closeSidebar: () => void
  toggleSidebarCollapsed: () => void
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
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      sidebarCollapsed: false,
      activePeriod: new Date().toISOString().slice(0, 7),
      notificationCount: 0,
      notificationItems: [],
      billingWarning: null,
      billingWarningDismissed: false,
      toggleSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      closeSidebar: () => set({ sidebarOpen: false }),
      toggleSidebarCollapsed: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
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
        activePeriod: state.activePeriod,
        notificationCount: state.notificationCount,
        notificationItems: state.notificationItems,
        billingWarning: state.billingWarning,
        billingWarningDismissed: state.billingWarningDismissed,
      }),
    },
  ),
)
