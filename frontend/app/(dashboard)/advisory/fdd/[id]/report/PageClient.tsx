"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { FDDReportViewer } from "@/components/advisory/fdd/FDDReportViewer"
import { FindingsTable } from "@/components/advisory/fdd/FindingsTable"
import { exportFDDReport, getFDDReport } from "@/lib/api/fdd"
import type { FDDReport } from "@/lib/types/fdd"

const sectionTabs: Array<{ key: string; label: string }> = [
  { key: "quality_of_earnings", label: "QoE" },
  { key: "working_capital", label: "Working Capital" },
  { key: "debt_liability", label: "Debt" },
  { key: "headcount", label: "Headcount" },
  { key: "revenue_quality", label: "Revenue Quality" },
]

export default function FDDReportPage() {
  const params = useParams()
  const engagementId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [report, setReport] = useState<FDDReport | null>(null)
  const [activeTab, setActiveTab] = useState("quality_of_earnings")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setReport(await getFDDReport(engagementId))
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load report")
      }
    }
    if (engagementId) {
      void load()
    }
  }, [engagementId])

  const currentSection = useMemo(() => {
    if (!report) return null
    return report.sections[activeTab] ?? null
  }, [activeTab, report])

  const doExport = async () => {
    const blob = await exportFDDReport(engagementId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `fdd_report_${engagementId}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">FDD Report</h1>
          <p className="text-sm text-muted-foreground">{report?.engagement.engagement_name ?? ""}</p>
        </div>
        <button
          type="button"
          onClick={doExport}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Export to Excel
        </button>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <article className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Executive Summary</h2>
        <p className="mt-2 text-sm text-foreground">{report?.executive_summary ?? "Loading..."}</p>
      </article>

      <div className="flex flex-wrap gap-2">
        {sectionTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-md border px-3 py-1.5 text-sm ${
              activeTab === tab.key
                ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.2)] text-foreground"
                : "border-border text-muted-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <FDDReportViewer sectionName={activeTab} resultData={currentSection} />
        <FindingsTable findings={report?.findings ?? []} />
      </div>
    </div>
  )
}
