"use client"

import { AlertTriangle } from "lucide-react"
import type { SubscriptionStatus as SubscriptionStatusType } from "@/types/billing"

interface SubscriptionStatusProps {
  status: SubscriptionStatusType
}

const statusStyles: Record<
  SubscriptionStatusType,
  { label: string; className: string; warning?: boolean }
> = {
  active: {
    label: "Active",
    className: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  },
  trialing: {
    label: "Trialing",
    className: "bg-[hsl(var(--brand-primary)/0.2)] text-[hsl(var(--brand-primary))]",
  },
  past_due: {
    label: "Past due",
    className: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  },
  grace_period: {
    label: "Grace period",
    className: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
    warning: true,
  },
  suspended: {
    label: "Suspended",
    className: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-muted text-muted-foreground",
  },
  incomplete: {
    label: "Incomplete",
    className: "bg-muted text-muted-foreground",
  },
}

export function SubscriptionStatus({ status }: SubscriptionStatusProps) {
  const config = statusStyles[status]
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${config.className}`}
    >
      {config.warning ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
      {config.label}
    </span>
  )
}
