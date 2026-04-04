import { STATUS_COLORS, type StatusKey } from "@/lib/config/tokens"
import { cn } from "@/lib/utils"

const normalizeStatus = (status: string): StatusKey | "default" => {
  const key = status.trim().toLowerCase().replace(/\s+/g, "_")
  return key in STATUS_COLORS ? (key as StatusKey) : "default"
}

/**
 * Shared pill badge for workflow and entity statuses.
 */
export interface StatusBadgeProps {
  status: string
  label?: string
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const statusKey = normalizeStatus(status)

  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-1 text-xs font-medium",
        STATUS_COLORS[statusKey],
        statusKey === "running" ? "animate-pulse" : "",
      )}
    >
      {label ?? status}
    </span>
  )
}
