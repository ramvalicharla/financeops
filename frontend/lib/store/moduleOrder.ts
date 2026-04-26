"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

interface ModuleOrderState {
  order: string[]
  setOrder: (order: string[]) => void
  reorder: (from: number, to: number) => void
  reset: () => void
}

export const useModuleOrderStore = create<ModuleOrderState>()(
  persist(
    (set) => ({
      order: [],
      setOrder: (order) => set({ order }),
      reorder: (from, to) =>
        set((state) => {
          const next = [...state.order]
          const [moved] = next.splice(from, 1)
          next.splice(to, 0, moved)
          return { order: next }
        }),
      reset: () => set({ order: [] }),
    }),
    {
      name: "finqor:module-order:v1",
      storage: createJSONStorage(() => localStorage),
    },
  ),
)
