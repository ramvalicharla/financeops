import type { ReactNode } from "react"

import { BadgeAlert, CircleCheckBig, CircleDashed, CircleHelp, CircleX } from "lucide-react"

import { STATUS_COLORS } from "@/lib/config/tokens"
import { cn } from "@/lib/utils"

export type StateBadgeTone =
  | "default"
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info"

const toneClassMap: Record<StateBadgeTone, string> = {
  default: STATUS_COLORS.default,
  neutral: STATUS_COLORS.default,
  success: STATUS_COLORS.success,
  warning: STATUS_COLORS.warning,
  danger: STATUS_COLORS.failed,
  info: STATUS_COLORS.running,
}

const toneIconMap: Record<StateBadgeTone, ReactNode> = {
  default: <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" />,
  neutral: <CircleDashed className="h-3.5 w-3.5" aria-hidden="true" />,
  success: <CircleCheckBig className="h-3.5 w-3.5" aria-hidden="true" />,
  warning: <BadgeAlert className="h-3.5 w-3.5" aria-hidden="true" />,
  danger: <CircleX className="h-3.5 w-3.5" aria-hidden="true" />,
  info: <CircleDashed className="h-3.5 w-3.5" aria-hidden="true" />,
}

const inferTone = (state: string): StateBadgeTone => {
  const normalized = state.trim().toLowerCase().replace(/\s+/g, "_")

  if (normalized.includes("error") || normalized.includes("fail")) {
    return "danger"
  }

  if (normalized.includes("warn") || normalized.includes("lock") || normalized.includes("review")) {
    return "warning"
  }

  if (
    normalized.includes("run") ||
    normalized.includes("active") ||
    normalized.includes("progress") ||
    normalized.includes("flight")
  ) {
    return "info"
  }

  if (
    normalized.includes("success") ||
    normalized.includes("complete") ||
    normalized.includes("approved") ||
    normalized.includes("posted") ||
    normalized.includes("closed")
  ) {
    return "success"
  }

  if (
    normalized.includes("pending") ||
    normalized.includes("draft") ||
    normalized.includes("inactive") ||
    normalized.includes("queued")
  ) {
    return "neutral"
  }

  return normalized in STATUS_COLORS ? "default" : "neutral"
}

export interface StateBadgeProps {
  state?: string
  status?: string
  label?: string
  tone?: StateBadgeTone
  className?: string
  showIcon?: boolean
}

/**
 * Shared governance badge for workflow, entity, and execution states.
 */
export function StateBadge({
  state,
  status,
  label,
  tone,
  className,
  showIcon = true,
}: StateBadgeProps) {
  const resolvedState = state ?? status ?? "unknown"
  const resolvedTone = tone ?? inferTone(resolvedState)
  const text = label ?? resolvedState

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium",
        toneClassMap[resolvedTone],
        className,
      )}
      title={text}
    >
      {showIcon ? toneIconMap[resolvedTone] : null}
      <span>{text}</span>
    </span>
  )
}
