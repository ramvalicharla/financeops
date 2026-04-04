"use client"

import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import {
  getDisplayPreferences,
  updateDisplayPreferences,
} from "@/lib/api/sprint11"
import { useDisplayScale } from "@/lib/store/displayScale"
import type { DisplayScale } from "@/lib/utils"

const FINANCE_LEADER_ROLES = new Set(["finance_leader", "platform_owner"])

export default function SettingsPage() {
  const { data: session } = useSession()
  const storeScale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)

  const [userScale, setUserScale] = useState<DisplayScale>(storeScale)
  const [tenantScale, setTenantScale] = useState<DisplayScale>("LAKHS")
  const [loading, setLoading] = useState(true)
  const [savingUser, setSavingUser] = useState(false)
  const [savingTenant, setSavingTenant] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isFinanceLeader = useMemo(() => {
    const role = session?.user?.role
    return role ? FINANCE_LEADER_ROLES.has(role) : false
  }, [session?.user?.role])

  useEffect(() => {
    let mounted = true
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const prefs = await getDisplayPreferences()
        if (!mounted) {
          return
        }
        setUserScale(prefs.user_override ?? prefs.effective_scale)
        setTenantScale(prefs.tenant_default)
        useDisplayScale.getState().setFromPreferences(prefs)
      } catch (cause) {
        if (!mounted) {
          return
        }
        setError(cause instanceof Error ? cause.message : "Failed to load display preferences")
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }
    void load()
    return () => {
      mounted = false
    }
  }, [])

  const handleScaleChange = async (scale: DisplayScale) => {
    setUserScale(scale)
    setScale(scale)
    setSavingUser(true)
    setError(null)
    setMessage(null)
    try {
      await updateDisplayPreferences({ user_scale: scale })
      setMessage("Personal display preference updated.")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update personal preference")
    } finally {
      setSavingUser(false)
    }
  }

  const handleTenantScaleChange = async (scale: DisplayScale) => {
    setTenantScale(scale)
    setSavingTenant(true)
    setError(null)
    setMessage(null)
    try {
      await updateDisplayPreferences({ tenant_scale: scale })
      setMessage("Company default display updated.")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update company default")
    } finally {
      setSavingTenant(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">Configure workspace display preferences.</p>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <h3 className="mb-3 text-sm font-medium text-foreground">Display & Formatting</h3>

        {loading ? <p className="text-sm text-muted-foreground">Loading display preferences...</p> : null}
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        {message ? <p className="text-sm text-emerald-400">{message}</p> : null}

        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm text-muted-foreground">
              Default Amount Display
            </label>
            <ScaleSelector
              value={userScale}
              onChange={handleScaleChange}
              size="md"
              showGroups
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Your personal preference. Overrides the company default.
            </p>
            {savingUser ? <p className="mt-1 text-xs text-muted-foreground">Saving...</p> : null}
          </div>

          {isFinanceLeader ? (
            <div>
              <label className="mb-2 block text-sm text-muted-foreground">
                Company Default Display
              </label>
              <ScaleSelector
                value={tenantScale}
                onChange={handleTenantScaleChange}
                size="md"
                showGroups
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Applied to all users who have not set a personal preference.
              </p>
              {savingTenant ? <p className="mt-1 text-xs text-muted-foreground">Saving...</p> : null}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}
