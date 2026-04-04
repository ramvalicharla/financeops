"use client"

import { FormField } from "@/components/ui/FormField"
import type { PlatformUserRole } from "@/lib/types/platform-admin"

export function RoleSelector({
  value,
  roles,
  onChange,
  disabled = false,
  id = "role-selector",
  label,
  error,
  hint,
  required = false,
}: {
  value: PlatformUserRole
  roles: PlatformUserRole[]
  onChange: (next: PlatformUserRole) => void
  disabled?: boolean
  id?: string
  label?: string
  error?: string
  hint?: string
  required?: boolean
}) {
  const control = (
    <select
      aria-label={label}
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

  if (!label) {
    return control
  }

  return (
    <FormField
      id={id}
      label={label}
      error={error}
      hint={hint}
      required={required}
    >
      {control}
    </FormField>
  )
}
