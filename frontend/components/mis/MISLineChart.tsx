"use client"

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { decimalStringToNumber } from "@/lib/utils"
import type { MISChartPoint } from "@/types/mis"

interface MISLineChartProps {
  data: MISChartPoint[]
}

export function MISLineChart({ data }: MISLineChartProps) {
  const { fmt, fmtNum, scaleLabel } = useFormattedAmount()

  const chartData = data.map((point) => ({
    ...point,
    revenueValue: decimalStringToNumber(point.revenue),
    grossProfitValue: decimalStringToNumber(point.gross_profit),
    ebitdaValue: decimalStringToNumber(point.ebitda),
  }))

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <h3 className="mb-1 text-lg font-semibold text-foreground">Trend (12 Months)</h3>
      <p className="mb-3 text-xs text-muted-foreground">{scaleLabel}</p>
      <div className="w-full h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              tickFormatter={(value) => fmtNum(value)}
            />
            <Tooltip
              contentStyle={{
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                backgroundColor: "hsl(var(--card))",
              }}
              formatter={(value) => fmt(value as number)}
            />
            <Line
              type="monotone"
              dataKey="revenueValue"
              name="Revenue"
              stroke="hsl(var(--brand-primary))"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="grossProfitValue"
              name="Gross Profit"
              stroke="hsl(var(--brand-success))"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="ebitdaValue"
              name="EBITDA"
              stroke="hsl(var(--brand-warning))"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
