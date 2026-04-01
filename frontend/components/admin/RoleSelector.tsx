"use client"

import type { PlatformUserRole } from "@/lib/types/platform-admin"

export function RoleSelector({
  value,
  roles,
  onChange,
  disabled = false,
}: {
  value: PlatformUserRole
  roles: PlatformUserRole[]
  onChange: (next: PlatformUserRole) => void
  disabled?: boolean
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value as PlatformUserRole)}
      disabled={disabled}
      className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:opacity-60"
    >
      {roles.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </select>
  )
}
