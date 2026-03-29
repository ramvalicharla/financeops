"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

interface UIState {
  sidebarOpen: boolean
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
      notificationCount: 0,
      notificationItems: [],
      billingWarning: null,
      billingWarningDismissed: false,
      toggleSidebar: () =>
        set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      closeSidebar: () => set({ sidebarOpen: false }),
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
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        notificationCount: state.notificationCount,
        notificationItems: state.notificationItems,
        billingWarning: state.billingWarning,
        billingWarningDismissed: state.billingWarningDismissed,
      }),
    },
  ),
)
