"use client"

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { decimalStringToNumber } from "@/lib/utils"

interface AllocationWaterfallProps {
  bookValueNetAssets: string
  totalIntangibles: string
  deferredTaxLiability: string
  goodwill: string
  purchasePrice: string
}

export function AllocationWaterfall({
  bookValueNetAssets,
  totalIntangibles,
  deferredTaxLiability,
  goodwill,
  purchasePrice,
}: AllocationWaterfallProps) {
  const chartData = [
    { label: "Book Value", value: decimalStringToNumber(bookValueNetAssets), fill: "#60A5FA" },
    { label: "+ Intangibles", value: decimalStringToNumber(totalIntangibles), fill: "#34D399" },
    { label: "- DTL", value: -decimalStringToNumber(deferredTaxLiability), fill: "#F59E0B" },
    { label: "Goodwill", value: decimalStringToNumber(goodwill), fill: "#A78BFA" },
    { label: "Purchase Price", value: decimalStringToNumber(purchasePrice), fill: "#F87171" },
  ]

  return (
    <div className="w-full h-72 rounded-xl border border-border bg-card p-4">
      <p className="mb-3 text-sm font-semibold text-foreground">Purchase Price Waterfall</p>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" />
          <YAxis stroke="hsl(var(--muted-foreground))" />
          <Tooltip />
          <Bar dataKey="value">
            {chartData.map((entry) => (
              <Cell key={entry.label} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
