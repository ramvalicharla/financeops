"use client"

import { useEffect, useState } from "react"
import { getWhiteLabelConfig, listWhiteLabelAuditLog } from "@/lib/api/white-label"
import type { WhiteLabelAuditLogRow, WhiteLabelConfig } from "@/lib/types/white-label"
import { BrandingEditor } from "@/components/white_label/BrandingEditor"
import { DomainConfig } from "@/components/white_label/DomainConfig"

export default function WhiteLabelSettingsPage() {
  const [config, setConfig] = useState<WhiteLabelConfig | null>(null)
  const [auditRows, setAuditRows] = useState<WhiteLabelAuditLogRow[]>([])
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const [configPayload, auditPayload] = await Promise.all([
        getWhiteLabelConfig(),
        listWhiteLabelAuditLog({ limit: 50, offset: 0 }),
      ])
      setConfig(configPayload)
      setAuditRows(auditPayload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load white label settings")
    }
  }

  useEffect(() => {
    void load()
  }, [])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">White Label Settings</h1>
        <p className="text-sm text-muted-foreground">Configure custom domain and tenant branding.</p>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      {config ? (
        <>
          <DomainConfig currentDomain={config.custom_domain ?? ""} verified={config.domain_verified} />
          <BrandingEditor initialConfig={config} />
          <section className="rounded-xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Audit Log</h2>
            </div>
            <div className="divide-y divide-border/60">
              {auditRows.map((row) => (
                <div key={row.id} className="px-4 py-3 text-sm">
                  <p className="text-foreground">{row.field_changed}</p>
                  <p className="text-xs text-muted-foreground">
                    {row.old_value ?? "-"} to {row.new_value ?? "-"}
                  </p>
                  <p className="text-[11px] text-muted-foreground">{row.created_at.slice(0, 19)}</p>
                </div>
              ))}
              {auditRows.length === 0 ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">No audit events yet.</p>
              ) : null}
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
