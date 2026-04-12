"use client"

import { QoEChart } from "@/components/advisory/fdd/QoEChart"
import { StructuredDataView } from "@/components/ui"

interface FDDReportViewerProps {
  sectionName: string
  resultData: Record<string, unknown> | null
  aiNarrative?: string | null
}

const getStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item))
}

export function FDDReportViewer({ sectionName, resultData, aiNarrative }: FDDReportViewerProps) {
  const safeResult = resultData ?? {}

  const title = sectionName.replaceAll("_", " ")
  const periods = getStringArray(safeResult.periods)

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-4">
      <header>
        <h3 className="text-base font-semibold capitalize text-foreground">{title}</h3>
      </header>

      {sectionName === "quality_of_earnings" ? (
        <QoEChart
          periods={periods}
          reported_ebitda={getStringArray(safeResult.reported_ebitda)}
          adjusted_ebitda={getStringArray(safeResult.adjusted_ebitda)}
        />
      ) : (
        <div className="rounded-md border border-border/60 bg-background p-3">
          <StructuredDataView
            data={safeResult}
            emptyMessage="No structured section data is available yet."
            compact
          />
        </div>
      )}

      <div className="rounded-md border border-border/60 bg-background p-3">
        <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">AI Narrative</p>
        <p className="mt-2 text-sm text-foreground">{aiNarrative ?? "Narrative pending."}</p>
      </div>
    </section>
  )
}
