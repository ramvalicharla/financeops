"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationsRead,
} from "@/lib/api/notifications"
import type { NotificationRow } from "@/lib/types/notifications"
import { NotificationItem } from "@/components/notifications/NotificationItem"

type NotificationPanelProps = {
  open: boolean
  onClose: () => void
  onUnreadCountChange?: (count: number) => void
}

export function NotificationPanel({
  open,
  onClose,
  onUnreadCountChange,
}: NotificationPanelProps) {
  const router = useRouter()
  const [rows, setRows] = useState<NotificationRow[]>([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    if (!open) {
      return
    }
    setLoading(true)
    try {
      const payload = await listNotifications({ limit: 12, offset: 0 })
      setRows(payload.notifications)
      onUnreadCountChange?.(payload.unread_count)
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [open])

  const onMarkAllRead = async () => {
    await markAllNotificationsRead()
    await load()
  }

  const onSelect = async (row: NotificationRow) => {
    if (!row.read_state.is_read) {
      await markNotificationsRead([row.id])
      onUnreadCountChange?.(Math.max(0, rows.filter((item) => !item.read_state.is_read).length - 1))
    }
    onClose()
    if (row.action_url) {
      router.push(row.action_url)
    } else {
      router.push("/notifications")
    }
  }

  if (!open) {
    return null
  }

  return (
    <div
      id="notifications-panel"
      role="dialog"
      aria-label="Notifications"
      className="absolute right-0 z-50 mt-2 w-[28rem] max-w-[92vw] rounded-xl border border-border bg-card p-3 shadow-2xl"
    >
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">Notifications</p>
        <button
          type="button"
          onClick={() => void onMarkAllRead()}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Mark all as read
        </button>
      </div>

      <div
        aria-live="polite"
        className="max-h-[26rem] space-y-2 overflow-y-auto"
      >
        {loading ? <p className="text-sm text-muted-foreground">Loading notifications...</p> : null}
        {!loading && rows.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-3 text-sm text-muted-foreground">
            You&apos;re all caught up.
          </p>
        ) : null}
        {rows.map((row) => (
          <NotificationItem key={row.id} notification={row} onSelect={onSelect} />
        ))}
      </div>

      <div className="mt-3 border-t border-border pt-2 text-right">
        <Link href="/notifications" className="text-xs text-muted-foreground hover:text-foreground">
          View all
        </Link>
      </div>
    </div>
  )
}
