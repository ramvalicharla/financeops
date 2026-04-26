"use client"

import { useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { X, Eye, AlertTriangle } from "lucide-react"
import { useTenantStore } from "@/lib/store/tenant"

/**
 * Sticky yellow banner rendered inside the Topbar when a platform owner has
 * switched into another tenant's context.  Also shows a one-shot warning when
 * the switch token expires (redirected back with ?switch_expired=1).
 */
export function ViewingAsBanner() {
  const isSwitched = useTenantStore((s) => s.is_switched)
  const switchMode = useTenantStore((s) => s.switch_mode)
  const tenantName = useTenantStore((s) => s.switched_tenant_name)
  const exitSwitchMode = useTenantStore((s) => s.exitSwitchMode)

  const searchParams = useSearchParams()
  const [expiredWarning, setExpiredWarning] = useState(false)

  // Show a flash warning if we were redirected back due to token expiry
  useEffect(() => {
    if (searchParams?.get("switch_expired") === "1") {
      setExpiredWarning(true)
      const t = setTimeout(() => setExpiredWarning(false), 6000)
      return () => clearTimeout(t)
    }
  }, [searchParams])

  if (!isSwitched && !expiredWarning) return null

  return (
    <>
      {expiredWarning && !isSwitched && (
        <div className="flex items-center justify-between gap-3 border-t border-amber-500/40 bg-amber-500/10 px-4 py-2 md:px-6">
          <div className="flex items-center gap-2 text-sm text-amber-300">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>Switch session expired. Returned to your own workspace.</span>
          </div>
          <button
            type="button"
            onClick={() => setExpiredWarning(false)}
            className="rounded p-0.5 text-amber-300/70 hover:text-amber-300 transition-colors"
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {isSwitched && switchMode === "admin" && (
        <div className="flex items-center justify-between gap-3 border-t border-amber-500/50 bg-amber-500/15 px-4 py-2 md:px-6">
          <div className="flex items-center gap-2 text-sm font-medium text-amber-200">
            <Eye className="h-4 w-4 shrink-0" />
            <span>
              Viewing as:{" "}
              <span className="font-semibold">{tenantName ?? "Unknown Org"}</span>
            </span>
            <span className="hidden sm:inline text-amber-300/60 text-xs font-normal">
              · Read-only · 15 min token
            </span>
          </div>
          <button
            type="button"
            onClick={exitSwitchMode}
            className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-200 hover:bg-amber-500/20 transition-colors"
            aria-label="Exit switched view"
          >
            <X className="h-3 w-3" />
            Exit
          </button>
        </div>
      )}
    </>
  )
}
