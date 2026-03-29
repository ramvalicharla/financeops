"use client"

import { useEffect } from "react"
import { getDisplayPreferences } from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"

export function DisplayPreferenceBootstrap() {
  useEffect(() => {
    let mounted = true
    void getDisplayPreferences()
      .then((prefs) => {
        if (!mounted) {
          return
        }
        useDisplayScale.getState().setFromPreferences(prefs)
      })
      .catch(() => {
        // Silent fallback to persisted local preference.
      })

    return () => {
      mounted = false
    }
  }, [])

  return null
}
