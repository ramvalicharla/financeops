"use client"

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { decimalStringToNumber } from "@/lib/utils"

interface QoEChartProps {
  periods: string[]
  reported_ebitda: string[]
  adjusted_ebitda: string[]
}

export function QoEChart({ periods, reported_ebitda, adjusted_ebitda }: QoEChartProps) {
  const chartData = periods.map((period, index) => {
    const reported = decimalStringToNumber(reported_ebitda[index] ?? "0")
    const adjusted = decimalStringToNumber(adjusted_ebitda[index] ?? "0")
    const marginPct = reported === 0 ? 0 : (adjusted / Math.abs(reported)) * 100
    return {
      period,
      reported,
      adjusted,
      marginPct,
    }
  })

  return (
    <div className="h-72 rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">Quality of Earnings Trend</p>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="period" stroke="hsl(var(--muted-foreground))" />
          <YAxis yAxisId="left" stroke="hsl(var(--muted-foreground))" />
          <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--muted-foreground))" />
          <Tooltip />
          <Legend />
          <Bar yAxisId="left" dataKey="reported" fill="#60A5FA" name="Reported EBITDA" />
          <Bar yAxisId="left" dataKey="adjusted" fill="#34D399" name="Adjusted EBITDA" />
          <Line yAxisId="right" type="monotone" dataKey="marginPct" stroke="#F59E0B" name="EBITDA Margin %" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
