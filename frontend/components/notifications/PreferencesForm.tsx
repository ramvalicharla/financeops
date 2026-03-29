"use client"

import { useEffect, useMemo, useState } from "react"
import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/lib/api/notifications"
import type { NotificationPreferences } from "@/lib/types/notifications"

const NOTIFICATION_TYPES = [
  "anomaly_detected",
  "close_deadline_approaching",
  "task_assigned",
  "approval_required",
  "budget_variance_alert",
  "expense_approved",
  "expense_rejected",
  "board_pack_ready",
  "erp_sync_failed",
  "system_alert",
] as const

const TIMEZONES = [
  "Asia/Kolkata",
  "UTC",
  "Europe/London",
  "America/New_York",
  "Asia/Singapore",
]

const normalizeTimeValue = (value: string | null): string => {
  if (!value) return ""
  return value.slice(0, 5)
}

export function PreferencesForm() {
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    setMessage(null)
    const payload = await getNotificationPreferences()
    setPreferences(payload)
  }

  useEffect(() => {
    void load()
  }, [])

  const typePreferences = useMemo(
    () => preferences?.type_preferences ?? {},
    [preferences?.type_preferences],
  )

  const toggleTypeChannel = (
    notificationType: string,
    channel: "email" | "inapp" | "push",
    value: boolean,
  ) => {
    if (!preferences) return
    setPreferences({
      ...preferences,
      type_preferences: {
        ...typePreferences,
        [notificationType]: {
          ...typePreferences[notificationType],
          [channel]: value,
        },
      },
    })
  }

  const onSave = async () => {
    if (!preferences) return
    setSaving(true)
    setMessage(null)
    try {
      const payload = await updateNotificationPreferences({
        email_enabled: preferences.email_enabled,
        inapp_enabled: preferences.inapp_enabled,
        push_enabled: preferences.push_enabled,
        quiet_hours_start: preferences.quiet_hours_start
          ? `${normalizeTimeValue(preferences.quiet_hours_start)}:00`
          : null,
        quiet_hours_end: preferences.quiet_hours_end
          ? `${normalizeTimeValue(preferences.quiet_hours_end)}:00`
          : null,
        timezone: preferences.timezone,
        type_preferences: preferences.type_preferences,
      })
      setPreferences(payload)
      setMessage("Preferences saved.")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to save preferences")
    } finally {
      setSaving(false)
    }
  }

  if (!preferences) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        Loading preferences...
      </div>
    )
  }

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-4">
      <header>
        <h2 className="text-base font-semibold text-foreground">Notification Preferences</h2>
        <p className="text-sm text-muted-foreground">
          Control delivery channels, quiet hours, and per-type overrides.
        </p>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
          <span>Email</span>
          <input
            type="checkbox"
            checked={preferences.email_enabled}
            onChange={(event) =>
              setPreferences({ ...preferences, email_enabled: event.target.checked })
            }
          />
        </label>
        <label className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
          <span>In-app</span>
          <input
            type="checkbox"
            checked={preferences.inapp_enabled}
            onChange={(event) =>
              setPreferences({ ...preferences, inapp_enabled: event.target.checked })
            }
          />
        </label>
        <label className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
          <span>Push</span>
          <input
            type="checkbox"
            checked={preferences.push_enabled}
            onChange={(event) =>
              setPreferences({ ...preferences, push_enabled: event.target.checked })
            }
          />
        </label>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm text-foreground">
          <span className="block text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Quiet Hours Start
          </span>
          <input
            type="time"
            value={normalizeTimeValue(preferences.quiet_hours_start)}
            onChange={(event) =>
              setPreferences({ ...preferences, quiet_hours_start: event.target.value || null })
            }
            className="w-full rounded-md border border-border bg-background px-3 py-2"
          />
        </label>
        <label className="space-y-1 text-sm text-foreground">
          <span className="block text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Quiet Hours End
          </span>
          <input
            type="time"
            value={normalizeTimeValue(preferences.quiet_hours_end)}
            onChange={(event) =>
              setPreferences({ ...preferences, quiet_hours_end: event.target.value || null })
            }
            className="w-full rounded-md border border-border bg-background px-3 py-2"
          />
        </label>
        <label className="space-y-1 text-sm text-foreground">
          <span className="block text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Timezone
          </span>
          <select
            value={preferences.timezone}
            onChange={(event) => setPreferences({ ...preferences, timezone: event.target.value })}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
          >
            {TIMEZONES.map((timezone) => (
              <option key={timezone} value={timezone}>
                {timezone}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Notification Type</th>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">In-app</th>
              <th className="px-3 py-2">Push</th>
            </tr>
          </thead>
          <tbody>
            {NOTIFICATION_TYPES.map((notificationType) => {
              const row = typePreferences[notificationType] ?? {}
              return (
                <tr key={notificationType} className="border-b border-border/50">
                  <td className="px-3 py-2 text-foreground">{notificationType}</td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={Boolean(row.email ?? true)}
                      onChange={(event) =>
                        toggleTypeChannel(notificationType, "email", event.target.checked)
                      }
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={Boolean(row.inapp ?? true)}
                      onChange={(event) =>
                        toggleTypeChannel(notificationType, "inapp", event.target.checked)
                      }
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={Boolean(row.push ?? false)}
                      onChange={(event) =>
                        toggleTypeChannel(notificationType, "push", event.target.checked)
                      }
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">{message ?? " "}</p>
        <button
          type="button"
          onClick={() => void onSave()}
          disabled={saving}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          {saving ? "Saving..." : "Save Preferences"}
        </button>
      </div>
    </section>
  )
}

