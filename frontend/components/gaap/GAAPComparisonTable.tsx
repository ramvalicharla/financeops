"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { type GAAPComparison } from "@/lib/types/sprint11"

export type GAAPComparisonTableProps = {
  comparison: GAAPComparison
  frameworks: string[]
}

const metrics: Array<{
  key: "revenue" | "gross_profit" | "ebitda" | "profit_before_tax" | "profit_after_tax"
  label: string
  diffKey: string
}> = [
  { key: "revenue", label: "Revenue", diffKey: "revenue_vs_indas" },
  { key: "gross_profit", label: "Gross Profit", diffKey: "gross_profit_vs_indas" },
  { key: "ebitda", label: "EBITDA", diffKey: "ebitda_vs_indas" },
  { key: "profit_before_tax", label: "PBT", diffKey: "profit_before_tax_vs_indas" },
  { key: "profit_after_tax", label: "PAT", diffKey: "profit_after_tax_vs_indas" },
]

export function GAAPComparisonTable({ comparison, frameworks }: GAAPComparisonTableProps) {
  const { fmt, scaleLabel } = useFormattedAmount()

  const frameworkMap = new Map(
    comparison.frameworks.map((row) => [row.gaap_framework.toUpperCase(), row]),
  )

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table aria-label="GAAP comparison" className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th scope="col" className="px-3 py-2 text-left text-xs text-muted-foreground">Metric</th>
            {frameworks.map((framework) => (
              <th key={framework} scope="col" className="px-3 py-2 text-right text-xs text-muted-foreground">{framework}</th>
            ))}
            <th scope="col" className="px-3 py-2 text-right text-xs text-muted-foreground">Difference vs INDAS</th>
          </tr>
          <tr className="border-b border-border/60">
            <th
              colSpan={frameworks.length + 2}
              className="px-3 py-2 text-left text-xs font-normal text-muted-foreground"
            >
              {scaleLabel}
            </th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.key} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-foreground">{metric.label}</td>
              {frameworks.map((framework) => (
                <td key={`${metric.key}-${framework}`} className="px-3 py-2 text-right text-foreground">
                  {fmt(frameworkMap.get(framework.toUpperCase())?.[metric.key] ?? null)}
                </td>
              ))}
              <td className="px-3 py-2 text-right text-foreground">
                {Object.entries(comparison.differences[metric.diffKey] ?? {}).map(
                  ([framework, value]) => {
                    const delta = Number.parseFloat(value)
                    return (
                      <div
                        key={`${metric.key}-${framework}`}
                        className={delta < 0 ? "text-red-400" : "text-emerald-400"}
                      >
                        {framework}: {fmt(value)}
                      </div>
                    )
                  },
                )}
              </td>
            </tr>
          ))}
          <tr className="border-t border-border">
            <td className="px-3 py-2 font-semibold text-foreground" colSpan={frameworks.length + 2}>
              Adjustments
            </td>
          </tr>
          {frameworks.map((framework) => (
            <tr key={`${framework}-adjustments`} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-muted-foreground">{framework}</td>
              <td className="px-3 py-2 text-foreground" colSpan={frameworks.length + 1}>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">
                  {JSON.stringify(frameworkMap.get(framework.toUpperCase())?.adjustments ?? [], null, 2)}
                </pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
