"use client"

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"

export type WeeklyBridgePoint = {
  week: string
  opening: number
  inflows: number
  outflows: number
  closing: number
}

export type WeeklyBridgeChartProps = {
  points: WeeklyBridgePoint[]
}

export function WeeklyBridgeChart({ points }: WeeklyBridgeChartProps) {
  const { fmt, scaleLabel } = useFormattedAmount()
  const chartData = points.map((point) => ({
    week: point.week,
    opening: point.opening,
    inflows: point.inflows,
    outflows: -Math.abs(point.outflows),
    closing: point.closing,
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Weekly Bridge</p>
      <p className="mt-1 text-xs text-muted-foreground">{scaleLabel}</p>
      <div className="mt-3 w-full h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="week" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                color: "hsl(var(--foreground))",
              }}
              formatter={(value) => {
                const numeric =
                  typeof value === "number"
                    ? value
                    : typeof value === "string"
                      ? Number.parseFloat(value)
                      : 0
                return [fmt(Number.isNaN(numeric) ? 0 : numeric), ""]
              }}
            />
            <Legend />
            <Bar dataKey="opening" fill="hsl(var(--muted-foreground))" />
            <Bar dataKey="inflows" fill="#22c55e" />
            <Bar dataKey="outflows" fill="#ef4444" />
            <Bar dataKey="closing" fill="hsl(var(--brand-primary))" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
