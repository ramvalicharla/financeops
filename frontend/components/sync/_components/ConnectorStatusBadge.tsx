"use client"

import { StatusBadge } from "@/components/ui/StatusBadge"

interface ConnectorStatusBadgeProps {
  label: string
  status: "active" | "success"
}

export function ConnectorStatusBadge({
  label,
  status,
}: ConnectorStatusBadgeProps) {
  return <StatusBadge status={status} label={label} />
}
