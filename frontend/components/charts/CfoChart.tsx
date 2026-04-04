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

export interface CfoChartDatum {
  period: string
  revenue: number
  profit: number
}

interface CfoChartProps {
  data: CfoChartDatum[]
}

export function CfoChart({ data }: CfoChartProps) {
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="period" />
          <YAxis />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="revenue"
            stroke="hsl(var(--brand-primary))"
          />
          <Line
            type="monotone"
            dataKey="profit"
            stroke="hsl(var(--brand-success))"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
