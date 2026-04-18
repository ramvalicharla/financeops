"use client"

import { useCallback, useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { AllocationWaterfall } from "@/components/advisory/ppa/AllocationWaterfall"
import { PPAReportViewer } from "@/components/advisory/ppa/PPAReportViewer"
import {
  exportPPAReport,
  getPPAEngagement,
  getPPAReport,
  identifyPPAIntangibles,
  runPPAEngagement,
} from "@/lib/api/ppa"
import type { PPAIntangibleSuggestion, PPAReport } from "@/lib/types/ppa"

export default function PPADetailPage() {
  const params = useParams()
  const engagementId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [report, setReport] = useState<PPAReport | null>(null)
  const [suggestions, setSuggestions] = useState<PPAIntangibleSuggestion[]>([])
  const [status, setStatus] = useState<string>("draft")
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const load = useCallback(async () => {
    try {
      const detail = await getPPAEngagement(engagementId)
      setStatus(detail.engagement.status)
      if (detail.engagement.status === "completed") {
        setReport(await getPPAReport(engagementId))
      } else {
        setReport(null)
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load engagement")
    }
  }, [engagementId])

  useEffect(() => {
    if (engagementId) {
      void load()
    }
  }, [engagementId, load])

  const identify = async () => {
    setError(null)
    try {
      setSuggestions(await identifyPPAIntangibles(engagementId))
    } catch (identifyError) {
      setError(identifyError instanceof Error ? identifyError.message : "Failed to identify intangibles")
    }
  }

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      const intangibles =
        suggestions.length > 0
          ? suggestions.map((row) => ({
              name: row.intangible_name,
              category: row.intangible_category,
              valuation_method: row.recommended_valuation_method,
              useful_life_years: row.typical_useful_life_years,
              assumptions: {
                revenue: "1000000",
                royalty_rate: "0.05",
                discount_rate: "0.12",
                useful_life_years: row.typical_useful_life_years,
                earnings: "350000",
                contributory_asset_charges: "120000",
              },
              tax_basis: "0",
              applicable_tax_rate: "0.25",
            }))
          : [
              {
                name: "Customer relationships",
                category: "customer_relationships",
                valuation_method: "excess_earnings",
                useful_life_years: "7",
                assumptions: {
                  earnings: "350000",
                  contributory_asset_charges: "120000",
                  discount_rate: "0.12",
                  useful_life_years: "7",
                },
                tax_basis: "0",
                applicable_tax_rate: "0.25",
              },
            ]
      await runPPAEngagement(engagementId, { intangibles })
      await load()
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Failed to run PPA")
    } finally {
      setRunning(false)
    }
  }

  const download = async () => {
    const blob = await exportPPAReport(engagementId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `ppa_report_${engagementId}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">PPA Engagement</h1>
          <p className="text-sm text-muted-foreground">Status: {status}</p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={identify} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
            Identify Intangibles
          </button>
          <button
            type="button"
            onClick={run}
            disabled={running}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
          >
            {running ? "Running..." : "Run Allocation"}
          </button>
          {report ? (
            <button type="button" onClick={download} className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
              Export
            </button>
          ) : null}
        </div>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      {suggestions.length > 0 ? (
        <article className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-sm font-semibold text-foreground">Suggested Intangibles</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {suggestions.map((row) => (
              <li key={`${row.intangible_name}-${row.intangible_category}`} className="rounded-md border border-border/60 bg-background px-3 py-2">
                <p className="text-foreground">{row.intangible_name}</p>
                <p className="text-xs text-muted-foreground">
                  {row.intangible_category} · {row.recommended_valuation_method}
                </p>
              </li>
            ))}
          </ul>
        </article>
      ) : null}

      {report ? (
        <PPAReportViewer report={report} />
      ) : (
        <AllocationWaterfall
          bookValueNetAssets="0"
          totalIntangibles="0"
          deferredTaxLiability="0"
          goodwill="0"
          purchasePrice="0"
        />
      )}
    </div>
  )
}
