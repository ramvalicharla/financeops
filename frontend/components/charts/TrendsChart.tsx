"use client"

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export interface TrendsChartDatum {
  period: string
  [key: string]: string | number | undefined
  revenue?: number
  expenses?: number
  profit?: number
  cash?: number
}

interface TrendsChartProps {
  data: TrendsChartDatum[]
}

export function TrendsChart({ data }: TrendsChartProps) {
  return (
    <div className="h-[420px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="revenue"
            stroke="hsl(var(--brand-primary))"
          />
          <Line
            type="monotone"
            dataKey="expenses"
            stroke="hsl(var(--brand-warning))"
          />
          <Line
            type="monotone"
            dataKey="profit"
            stroke="hsl(var(--brand-success))"
          />
          <Line
            type="monotone"
            dataKey="cash"
            stroke="hsl(var(--brand-secondary))"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
