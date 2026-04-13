"use client"

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { decimalStringToNumber } from "@/lib/utils"

interface WaterfallChartProps {
  waterfall: {
    base_ebitda: string
    drivers: Array<{ driver_name: string; impact: string }>
    optimistic_ebitda: string
    pessimistic_ebitda: string
  }
}

export function WaterfallChart({ waterfall }: WaterfallChartProps) {
  const data = [
    { name: "Pessimistic", value: decimalStringToNumber(waterfall.pessimistic_ebitda), fill: "#DC2626" },
    ...waterfall.drivers.map((driver) => ({
      name: driver.driver_name,
      value: decimalStringToNumber(driver.impact),
      fill: decimalStringToNumber(driver.impact) >= 0 ? "#16A34A" : "#DC2626",
    })),
    { name: "Optimistic", value: decimalStringToNumber(waterfall.optimistic_ebitda), fill: "#16A34A" },
  ]

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold text-foreground">EBITDA Waterfall</h2>
      <div className="w-full h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip />
            <Bar dataKey="value" fill="#60A5FA">
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}
