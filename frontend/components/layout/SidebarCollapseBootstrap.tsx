"use client"

import { useEffect, useRef } from "react"
import { getUserPreferences, updateUserPreferences } from "@/lib/api/userPreferences"
import { useWorkspaceStore } from "@/lib/store/workspace"

const DEBOUNCE_MS = 250

export function SidebarCollapseBootstrap() {
  const sidebarCollapsed = useWorkspaceStore((s) => s.sidebarCollapsed)
  const setSidebarCollapsed = useWorkspaceStore((s) => s.setSidebarCollapsed)

  // bootstrapped: true once the initial server fetch has resolved (or errored).
  const bootstrapped = useRef(false)
  // lastSynced: tracks the last value we received from / sent to the server.
  // Used to skip the debounced PATCH when the change was caused by seeding from server.
  const lastSynced = useRef<boolean | null>(null)
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // On mount: fetch server preference; let server win if non-null.
  useEffect(() => {
    let mounted = true
    void getUserPreferences()
      .then((prefs) => {
        if (!mounted) return
        bootstrapped.current = true
        if (prefs.sidebar_collapsed !== null && prefs.sidebar_collapsed !== undefined) {
          lastSynced.current = prefs.sidebar_collapsed
          setSidebarCollapsed(prefs.sidebar_collapsed)
        } else {
          // Server has no preference — keep localStorage value as-is.
          lastSynced.current = useWorkspaceStore.getState().sidebarCollapsed
        }
      })
      .catch(() => {
        // Silent fallback — localStorage value remains authoritative.
        bootstrapped.current = true
        lastSynced.current = useWorkspaceStore.getState().sidebarCollapsed
      })
    return () => {
      mounted = false
    }
  }, [setSidebarCollapsed])

  // On toggle: debounced PATCH to server.
  // Skips if bootstrap hasn't completed or value matches last synced (avoids
  // firing a PATCH immediately after seeding from server).
  useEffect(() => {
    if (!bootstrapped.current) return
    if (lastSynced.current === sidebarCollapsed) return

    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => {
      lastSynced.current = sidebarCollapsed
      void updateUserPreferences({ sidebar_collapsed: sidebarCollapsed }).catch(() => {
        console.warn("[SidebarCollapseBootstrap] Failed to sync sidebar preference to server")
      })
    }, DEBOUNCE_MS)

    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [sidebarCollapsed])

  return null
}
