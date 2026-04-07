"use client"

import { useEffect, useMemo, useState } from "react"
import { listOwnConsent, recordConsent } from "@/lib/api/compliance"
import { ConsentToggle } from "@/components/settings/ConsentToggle"

type ConsentRow = {
  consent_type: string
  granted: boolean
  granted_at: string | null
  withdrawn_at: string | null
  lawful_basis: string
}

const CONSENTS = [
  {
    consent_type: "analytics",
    label: "Analytics",
    description: "Help improve product quality through usage analytics.",
  },
  {
    consent_type: "marketing",
    label: "Marketing",
    description: "Receive product updates and promotional emails.",
  },
  {
    consent_type: "ai_processing",
    label: "AI Processing",
    description: "Allow AI-based insights on your financial data.",
  },
  {
    consent_type: "data_sharing",
    label: "Data Sharing",
    description: "Allow controlled sharing with integrated partners.",
  },
  {
    consent_type: "performance_monitoring",
    label: "Performance Monitoring",
    description: "Allow telemetry for reliability and incident response.",
  },
] as const

export default function PrivacyConsentPage() {
  const [rows, setRows] = useState<Record<string, ConsentRow>>({})
  const [pending, setPending] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const load = async () => {
      const values = await listOwnConsent()
      const map: Record<string, ConsentRow> = {}
      for (const value of values) {
        const row = value as ConsentRow
        map[row.consent_type] = row
      }
      setRows(map)
      setPending(
        Object.fromEntries(
          CONSENTS.map((item) => [item.consent_type, map[item.consent_type]?.granted ?? false]),
        ),
      )
    }
    void load()
  }, [])

  const dirty = useMemo(
    () =>
      CONSENTS.some(
        (item) => (rows[item.consent_type]?.granted ?? false) !== (pending[item.consent_type] ?? false),
      ),
    [pending, rows],
  )

  const save = async () => {
    setSaving(true)
    try {
      for (const item of CONSENTS) {
        const granted = pending[item.consent_type] ?? false
        const current = rows[item.consent_type]?.granted ?? false
        if (granted === current) {
          continue
        }
        await recordConsent({ consent_type: item.consent_type, granted, lawful_basis: "consent" })
      }
      const values = await listOwnConsent()
      const map: Record<string, ConsentRow> = {}
      for (const value of values) {
        const row = value as ConsentRow
        map[row.consent_type] = row
      }
      setRows(map)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Consent Preferences</h1>
        <p className="text-sm text-muted-foreground">Manage your consent settings and lawful basis disclosures.</p>
      </header>

      <section className="space-y-3">
        {CONSENTS.map((item) => {
          const row = rows[item.consent_type]
          return (
            <ConsentToggle
              key={item.consent_type}
              consentType={item.consent_type}
              label={item.label}
              description={item.description}
              granted={pending[item.consent_type] ?? row?.granted ?? false}
              grantedAt={row?.granted_at}
              withdrawnAt={row?.withdrawn_at}
              onChange={(next) =>
                setPending((current) => ({
                  ...current,
                  [item.consent_type]: next,
                }))
              }
            />
          )
        })}
      </section>

      <button
        type="button"
        onClick={() => void save()}
        disabled={!dirty || saving}
        className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save preferences"}
      </button>
    </div>
  )
}

