"use client"

import { create } from "zustand"

interface ModuleManagerState {
  isOpen: boolean
  open: () => void
  close: () => void
  toggle: () => void
}

export const useModuleManagerStore = create<ModuleManagerState>()((set) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
}))
