"use client"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"

export type CashPositionCardProps = {
  opening: string
  minimum: string
  minimumWeek: number
  closing: string
  isCashPositive: boolean
}

export function CashPositionCard({
  opening,
  minimum,
  minimumWeek,
  closing,
  isCashPositive,
}: CashPositionCardProps) {
  const { fmt, scaleLabel } = useFormattedAmount()

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Cash Position</p>
      <p className="mt-1 text-xs text-muted-foreground">{scaleLabel}</p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <p className="text-xs text-muted-foreground">Opening</p>
          <p className="text-lg font-semibold text-foreground">{fmt(opening)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Minimum (Week {minimumWeek})</p>
          <p className="text-lg font-semibold text-foreground">{fmt(minimum)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Week 13 Closing</p>
          <p className="text-lg font-semibold text-foreground">{fmt(closing)}</p>
        </div>
      </div>
      {!isCashPositive ? (
        <p className="mt-3 rounded-md border border-[hsl(var(--brand-danger)/0.5)] bg-[hsl(var(--brand-danger)/0.12)] px-3 py-2 text-xs text-[hsl(var(--brand-danger))]">
          Warning: one or more forecast weeks drop below zero.
        </p>
      ) : null}
    </div>
  )
}
