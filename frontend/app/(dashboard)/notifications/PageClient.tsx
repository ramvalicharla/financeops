"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationsRead,
} from "@/lib/api/notifications"
import type { NotificationRow } from "@/lib/types/notifications"
import { NotificationItem } from "@/components/notifications/NotificationItem"
import { PreferencesForm } from "@/components/notifications/PreferencesForm"

export default function NotificationsPage() {
  const [rows, setRows] = useState<NotificationRow[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filterType, setFilterType] = useState("")

  const availableTypes = useMemo(
    () => Array.from(new Set(rows.map((row) => row.notification_type))).sort(),
    [rows],
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const payload = await listNotifications({
        type: filterType || undefined,
        limit: 100,
        offset: 0,
      })
      setRows(payload.notifications)
      setUnreadCount(payload.unread_count)
    } finally {
      setLoading(false)
    }
  }, [filterType])

  useEffect(() => {
    void load()
  }, [filterType, load])

  const onMarkAll = async () => {
    await markAllNotificationsRead()
    await load()
  }

  const onSelect = async (row: NotificationRow) => {
    if (!row.read_state.is_read) {
      await markNotificationsRead([row.id])
      await load()
    }
    if (row.action_url) {
      window.location.assign(row.action_url)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Notifications</h1>
          <p className="text-sm text-muted-foreground">
            Alerts and updates across anomalies, approvals, close workflows, and reports.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
            Unread: {unreadCount}
          </span>
          <button
            type="button"
            onClick={() => void onMarkAll()}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Mark all as read
          </button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <label className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Filter by type</label>
        <select
          value={filterType}
          onChange={(event) => setFilterType(event.target.value)}
          className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground md:w-80"
        >
          <option value="">All types</option>
          {availableTypes.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </section>

      <section className="space-y-2">
        {loading ? <p className="text-sm text-muted-foreground">Loading notifications...</p> : null}
        {!loading && rows.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            You&apos;re all caught up.
          </p>
        ) : null}
        {rows.map((row) => (
          <NotificationItem key={row.id} notification={row} onSelect={onSelect} />
        ))}
      </section>

      <PreferencesForm />
    </div>
  )
}

