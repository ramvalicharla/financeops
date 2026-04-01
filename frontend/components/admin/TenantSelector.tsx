"use client"

import type { PlatformTenant } from "@/lib/types/platform-admin"

export function TenantSelector({
  tenants,
  value,
  onChange,
  disabled = false,
}: {
  tenants: PlatformTenant[]
  value: string
  onChange: (tenantId: string) => void
  disabled?: boolean
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground disabled:opacity-60"
    >
      <option value="">Select tenant</option>
      {tenants.map((tenant) => (
        <option key={tenant.id} value={tenant.id}>
          {tenant.display_name} ({tenant.slug})
        </option>
      ))}
    </select>
  )
}
