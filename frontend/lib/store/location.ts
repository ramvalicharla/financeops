"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

interface LocationState {
  active_location_id: string | null
  setActiveLocation: (id: string | null) => void
  clearLocation: () => void
}

const initialState = {
  active_location_id: null as string | null,
}

export const useLocationStore = create<LocationState>()(
  persist(
    (set) => ({
      ...initialState,
      setActiveLocation: (id) => set({ active_location_id: id }),
      clearLocation: () => set(initialState),
    }),
    {
      name: "financeops-location-store",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        active_location_id: state.active_location_id,
      }),
    },
  ),
)
