"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

interface AgingBarDatum {
  bucket: string
  value: number
}

interface WorkingCapitalChartProps {
  title: string
  data: AgingBarDatum[]
  barColor: string
}

export function WorkingCapitalChart({
  title,
  data,
  barColor,
}: WorkingCapitalChartProps) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">{title}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="bucket" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip />
            <Bar dataKey="value" fill={barColor} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}
