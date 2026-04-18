"use client"

import Link from "next/link"
import { useCallback, useEffect, useState } from "react"
import { enableWhiteLabelTenant, listWhiteLabelAdminConfigs } from "@/lib/api/white-label"
import type { WhiteLabelConfig } from "@/lib/types/white-label"

export default function AdminWhiteLabelPage() {
  const [rows, setRows] = useState<WhiteLabelConfig[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const payload = await listWhiteLabelAdminConfigs({ limit: 200, offset: 0 })
      setRows(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load white label tenants")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const enable = async (tenantId: string) => {
    setMessage(null)
    setError(null)
    try {
      await enableWhiteLabelTenant(tenantId)
      setMessage("White label enabled for tenant.")
      await load()
    } catch (enableError) {
      setError(enableError instanceof Error ? enableError.message : "Failed to enable white label")
    }
  }

  const statusFor = (row: WhiteLabelConfig): string => {
    if (row.is_enabled) {
      return "enabled"
    }
    if (row.custom_domain) {
      return "pending"
    }
    return "disabled"
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">White Label Tenants</h1>
        <p className="text-sm text-muted-foreground">Enable and review custom domain and branding status per tenant.</p>
      </header>

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="overflow-x-auto">
          <table aria-label="White label configurations" className="min-w-full text-sm">
            <thead className="bg-background/50 text-xs uppercase tracking-[0.14em] text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 text-left">Tenant ID</th>
                <th scope="col" className="px-4 py-3 text-left">Domain</th>
                <th scope="col" className="px-4 py-3 text-left">Status</th>
                <th scope="col" className="px-4 py-3 text-left">Verified</th>
                <th scope="col" className="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="px-4 py-3 text-foreground">{row.tenant_id}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.custom_domain ?? "-"}</td>
                  <td className="px-4 py-3 text-muted-foreground">{statusFor(row)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.domain_verified ? "yes" : "no"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {!row.is_enabled ? (
                        <button
                          type="button"
                          onClick={() => void enable(row.tenant_id)}
                          className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
                        >
                          Enable
                        </button>
                      ) : null}
                      <Link
                        href={`/admin/white-label/${row.tenant_id}`}
                        className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
                      >
                        Open
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-5 text-center text-sm text-muted-foreground">
                    No white label configurations found.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
