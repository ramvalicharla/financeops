"use client"

import { formatDistanceToNowStrict } from "date-fns"
import {
  AlertTriangle,
  BadgeCheck,
  Bell,
  BriefcaseBusiness,
  CalendarClock,
  CircleDollarSign,
  ClockAlert,
  FileCheck2,
  FileWarning,
  ShieldAlert,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { NotificationRow } from "@/lib/types/notifications"

type NotificationItemProps = {
  notification: NotificationRow
  onSelect: (notification: NotificationRow) => void
}

const iconForType = (type: string) => {
  if (type.includes("anomaly")) return AlertTriangle
  if (type.includes("close")) return ClockAlert
  if (type.includes("task")) return CalendarClock
  if (type.includes("approval")) return BadgeCheck
  if (type.includes("expense")) return CircleDollarSign
  if (type.includes("board_pack") || type.includes("report")) return FileCheck2
  if (type.includes("failed") || type.includes("rejected")) return FileWarning
  if (type.includes("fdd") || type.includes("ppa")) return BriefcaseBusiness
  if (type.includes("system")) return ShieldAlert
  return Bell
}

export function NotificationItem({ notification, onSelect }: NotificationItemProps) {
  const Icon = iconForType(notification.notification_type)
  const relative = formatDistanceToNowStrict(new Date(notification.created_at), {
    addSuffix: true,
  })

  return (
    <button
      type="button"
      onClick={() => onSelect(notification)}
      className={cn(
        "flex w-full items-start gap-3 rounded-md border px-3 py-2 text-left transition",
        notification.read_state.is_read
          ? "border-transparent hover:bg-accent"
          : "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.14)] hover:bg-[hsl(var(--brand-primary)/0.2)]",
      )}
    >
      <span className="mt-0.5 rounded-md border border-border bg-background p-1.5 text-muted-foreground">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{notification.title}</span>
          {!notification.read_state.is_read ? (
            <span className="h-2 w-2 rounded-full bg-[hsl(var(--brand-primary))]" />
          ) : null}
        </span>
        <span className="mt-0.5 block overflow-hidden text-xs text-muted-foreground [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">
          {notification.body}
        </span>
      </span>
      <span className="whitespace-nowrap text-[11px] text-muted-foreground">{relative}</span>
    </button>
  )
}

