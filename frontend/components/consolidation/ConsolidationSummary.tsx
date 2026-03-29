"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { formatINR } from "@/lib/utils"
import type { ConsolidationSummary as ConsolidationSummaryData } from "@/types/consolidation"

interface ConsolidationSummaryProps {
  summary: ConsolidationSummaryData | null
  isLoading: boolean
}

export function ConsolidationSummary({
  summary,
  isLoading,
}: ConsolidationSummaryProps) {
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)

  const metricRows = useMemo(
    () => [
      { key: "consolidated_revenue", label: "Consolidated Revenue" },
      { key: "consolidated_gross_profit", label: "Consolidated Gross Profit" },
      { key: "consolidated_ebitda", label: "Consolidated EBITDA" },
      { key: "consolidated_net_profit", label: "Consolidated Net Profit" },
      { key: "intercompany_eliminations", label: "Intercompany Eliminations" },
      { key: "fx_translation_difference", label: "FX Translation Difference" },
    ],
    [],
  )

  if (isLoading) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="h-72 animate-pulse rounded-md bg-muted/30" />
      </section>
    )
  }

  if (!summary) {
    return (
      <section className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">
          Select entities and click Run Consolidation.
        </p>
      </section>
    )
  }

  return (
    <>
      <section className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-3 text-lg font-semibold text-foreground">
          Consolidation Summary
        </h3>
        <div className="space-y-2">
          {metricRows.map((row) => (
            <button
              key={row.key}
              type="button"
              className="flex w-full items-center justify-between rounded-md border border-border px-3 py-3 text-left hover:bg-accent/30"
              onClick={() => setSelectedMetric(row.key)}
            >
              <span className="text-sm text-foreground">{row.label}</span>
              <span className="text-sm font-medium text-foreground">
                {formatINR(
                  String(
                    summary[
                      row.key as keyof Pick<
                        ConsolidationSummaryData,
                        | "consolidated_revenue"
                        | "consolidated_gross_profit"
                        | "consolidated_ebitda"
                        | "consolidated_net_profit"
                        | "intercompany_eliminations"
                        | "fx_translation_difference"
                      >
                    ],
                  ),
                )}
              </span>
            </button>
          ))}
        </div>
      </section>

      {selectedMetric ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="max-h-[85vh] w-full max-w-5xl overflow-y-auto rounded-lg border border-border bg-card p-5">
            <div className="mb-4 flex items-center justify-between">
              <h4 className="text-lg font-semibold text-foreground">
                Entity Breakdown
              </h4>
              <Button
                size="sm"
                type="button"
                variant="outline"
                onClick={() => setSelectedMetric(null)}
              >
                Close
              </Button>
            </div>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[1000px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Entity
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Currency
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      FX Rate
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Revenue Local
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Revenue INR
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Gross Profit INR
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      EBITDA INR
                    </th>
                    <th className="px-3 py-2 text-right font-medium text-foreground">
                      Net Profit INR
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {summary.entity_breakdown.map((row) => (
                    <tr key={row.entity_id} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">
                        {row.entity_name.replaceAll(" ", " · ")}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {row.currency}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.fx_rate)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.revenue_local)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.revenue_inr)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.gross_profit_inr)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.ebitda_inr)}
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">
                        {formatINR(row.net_profit_inr)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
