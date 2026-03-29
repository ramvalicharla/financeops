"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { listWhiteLabelAdminConfigs } from "@/lib/api/white-label"
import type { WhiteLabelConfig } from "@/lib/types/white-label"
import { BrandingEditor } from "@/components/white_label/BrandingEditor"
import { DomainConfig } from "@/components/white_label/DomainConfig"

export default function AdminWhiteLabelTenantPage() {
  const params = useParams()
  const tenantId = Array.isArray(params?.tenant_id) ? params.tenant_id[0] : params?.tenant_id ?? ""
  const [config, setConfig] = useState<WhiteLabelConfig | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const payload = await listWhiteLabelAdminConfigs({ limit: 500, offset: 0 })
      const match = payload.data.find((row) => row.tenant_id === tenantId) ?? null
      setConfig(match)
      if (!match) {
        setError("White label config not found for this tenant.")
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load tenant white label config")
    }
  }

  useEffect(() => {
    if (tenantId) {
      void load()
    }
  }, [tenantId])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Tenant White Label</h1>
        <p className="text-sm text-muted-foreground">Tenant ID: {tenantId}</p>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      {config ? (
        <>
          <DomainConfig
            currentDomain={config.custom_domain ?? ""}
            verified={config.domain_verified}
            readOnly
          />
          <BrandingEditor initialConfig={config} readOnly />
          <section className="rounded-xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground">Audit Log</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Tenant audit history is available through the tenant white-label endpoint. Platform view exposes
              current config and status.
            </p>
          </section>
        </>
      ) : null}
    </div>
  )
}
