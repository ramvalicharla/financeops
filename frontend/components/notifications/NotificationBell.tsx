"use client"

import { useCallback, useEffect, useState } from "react"
import { Bell } from "lucide-react"
import { getUnreadNotificationCount } from "@/lib/api/notifications"
import { useUIStore } from "@/lib/store/ui"
import { NotificationPanel } from "@/components/notifications/NotificationPanel"

interface NotificationBellProps {
  onTrigger?: () => void
}

const MAX_NOTIFICATION_REFRESH_ATTEMPTS = 120

export function NotificationBell({ onTrigger }: NotificationBellProps = {}) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const setStoreCount = useUIStore((state) => state.setNotificationCount)

  const refreshCount = useCallback(async () => {
    try {
      const unread = await getUnreadNotificationCount()
      setCount(unread)
      setStoreCount(unread)
    } catch {
      setCount(0)
      setStoreCount(0)
    }
  }, [setStoreCount])

  useEffect(() => {
    void refreshCount()
    let attempts = 0
    const timer = setInterval(() => {
      if (attempts >= MAX_NOTIFICATION_REFRESH_ATTEMPTS) {
        clearInterval(timer)
        return
      }
      attempts += 1
      void refreshCount()
    }, 30_000)
    return () => clearInterval(timer)
  }, [refreshCount])

  return (
    <div className="relative">
      <button
        className="relative rounded-md border border-border p-2 text-foreground"
        onClick={() => {
          onTrigger?.()
          setOpen((prev) => !prev)
        }}
        type="button"
        aria-label="Notifications"
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls="notifications-panel"
      >
        <Bell className="h-4 w-4" />
        {count > 0 ? (
          <span className="absolute -right-1 -top-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-[hsl(var(--brand-danger))] px-1 text-[10px] font-semibold text-white">
            {count > 99 ? "99+" : count}
          </span>
        ) : null}
      </button>
      <NotificationPanel
        open={open}
        onClose={() => setOpen(false)}
        onUnreadCountChange={(next) => {
          setCount(next)
          setStoreCount(next)
        }}
      />
    </div>
  )
}
