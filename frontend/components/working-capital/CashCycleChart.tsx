"use client"

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts"
import { decimalStringToNumber } from "@/lib/utils"
import type { WCTrendPoint } from "@/lib/types/working-capital"

interface CashCycleChartProps {
  trends: WCTrendPoint[]
}

export function CashCycleChart({ trends }: CashCycleChartProps) {
  const chartData = trends
    .slice()
    .reverse()
    .map((row) => ({
      period: row.period,
      dso: decimalStringToNumber(row.dso_days),
      dpo: decimalStringToNumber(row.dpo_days),
      ccc: decimalStringToNumber(row.ccc_days),
    }))

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Cash Cycle (12 Months)</h3>
      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="period" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="dso" stroke="#60A5FA" strokeWidth={2} dot={false} name="DSO" />
            <Line type="monotone" dataKey="dpo" stroke="#F59E0B" strokeWidth={2} dot={false} name="DPO" />
            <Line type="monotone" dataKey="ccc" stroke="#2DD4BF" strokeWidth={2} dot={false} name="CCC" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
