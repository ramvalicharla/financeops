"use client"

import { useCallback, useEffect, useState } from "react"
import { getConsentSummary } from "@/lib/api/compliance"
import type { ConsentSummary } from "@/lib/types/compliance"
import { ConsentCoverageTable } from "@/components/trust/ConsentCoverageTable"

export default function TrustGdprConsentPage() {
  const [summary, setSummary] = useState<ConsentSummary | null>(null)

  useEffect(() => {
    const load = async () => {
      setSummary(await getConsentSummary())
    }
    void load()
  }, [])

  const exportCsv = () => {
    if (!summary) return
    const header = "consent_type,granted_count,withdrawn_count,coverage_pct"
    const lines = summary.consent.map(
      (row) => `${row.consent_type},${row.granted_count},${row.withdrawn_count},${row.coverage_pct}`,
    )
    const blob = new Blob([[header, ...lines].join("\n")], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "consent_coverage.csv"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Consent Coverage</h1>
          <p className="text-sm text-muted-foreground">Coverage per consent type across your tenant.</p>
        </div>
        <button type="button" onClick={exportCsv} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Export Consent Report
        </button>
      </header>
      {summary ? <ConsentCoverageTable summary={summary} /> : null}
    </div>
  )
}

