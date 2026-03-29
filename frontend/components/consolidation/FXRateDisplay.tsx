"use client"

import { formatINR } from "@/lib/utils"

interface FXRateDisplayProps {
  currency: string
  rate: string
}

export function FXRateDisplay({ currency, rate }: FXRateDisplayProps) {
  const isINR = currency.toUpperCase() === "INR"
  return (
    <span
      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
        isINR
          ? "bg-muted text-muted-foreground"
          : "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]"
      }`}
    >
      {currency.toUpperCase()} @ {formatINR(rate)}
    </span>
  )
}
