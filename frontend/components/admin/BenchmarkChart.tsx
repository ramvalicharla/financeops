"use client"

import { useMemo } from "react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { BenchmarkResult } from "@/lib/types/learning"

type BenchmarkChartProps = {
  results: BenchmarkResult[]
}

const COLORS = ["#60A5FA", "#34D399", "#F59E0B", "#A78BFA", "#FB7185"]

type ChartPoint = {
  date: string
} & Record<string, number | string>

const toPercent = (accuracy: string): number => {
  const numeric = Number.parseFloat(accuracy)
  if (!Number.isFinite(numeric)) return 0
  return numeric * 100
}

export function BenchmarkChart({ results }: BenchmarkChartProps) {
  const { data, benchmarkNames } = useMemo(() => {
    const names = Array.from(new Set(results.map((row) => row.benchmark_name))).sort()
    const grouped = new Map<string, ChartPoint>()

    for (const row of results) {
      const date = new Date(row.run_at).toISOString().slice(0, 10)
      const existing = grouped.get(date) ?? { date }
      existing[row.benchmark_name] = toPercent(row.accuracy_pct)
      grouped.set(date, existing)
    }

    const chartData = Array.from(grouped.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    )
    return { data: chartData, benchmarkNames: names }
  }, [results])

  return (
    <div className="w-full h-80 rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">Benchmark Accuracy Trend</p>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" />
          <YAxis
            stroke="hsl(var(--muted-foreground))"
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
          />
          <Tooltip
            formatter={(value) => {
              const numeric =
                typeof value === "number"
                  ? value
                  : Number.parseFloat(String(Array.isArray(value) ? value[0] : value))
              if (!Number.isFinite(numeric)) {
                return "0.00%"
              }
              return `${numeric.toFixed(2)}%`
            }}
          />
          <Legend />
          <ReferenceLine
            y={85}
            stroke="#60A5FA"
            strokeDasharray="4 4"
            label={{ value: "Target 85%", position: "right", fill: "#60A5FA" }}
          />
          {benchmarkNames.map((name, index) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={COLORS[index % COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
