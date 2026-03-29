"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"
import type { DisplayScale } from "@/lib/utils"

interface DisplayScaleState {
  scale: DisplayScale
  currency: string
  locale: string
  setScale: (scale: DisplayScale) => void
  setCurrency: (currency: string) => void
  setFromPreferences: (prefs: {
    effective_scale: DisplayScale
    currency: string
    locale: string
  }) => void
}

export const useDisplayScale = create<DisplayScaleState>()(
  persist(
    (set) => ({
      scale: "INR",
      currency: "₹",
      locale: "en-IN",

      setScale: (scale) => set({ scale }),
      setCurrency: (currency) => set({ currency }),
      setFromPreferences: (prefs) =>
        set({
          scale: prefs.effective_scale,
          currency: prefs.currency === "INR" ? "₹" : prefs.currency,
          locale: prefs.locale,
        }),
    }),
    {
      name: "financeops-display-scale",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        scale: state.scale,
        currency: state.currency,
        locale: state.locale,
      }),
    },
  ),
)
