"use client"

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import type { MISDashboard as MISDashboardData } from "@/types/mis"

interface MISDashboardProps {
  dashboard: MISDashboardData | null
}

const parsePercent = (value: string): number => {
  const parsed = Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const changeTone = (value: string): "positive" | "negative" | "neutral" => {
  const parsed = parsePercent(value)
  if (parsed > 0) {
    return "positive"
  }
  if (parsed < 0) {
    return "negative"
  }
  return "neutral"
}

export function MISDashboard({ dashboard }: MISDashboardProps) {
  const { fmt, scaleLabel } = useFormattedAmount()

  const cards = [
    {
      title: "Topline",
      value: dashboard?.revenue ?? "0",
      change: dashboard?.revenue_change_pct ?? "0",
    },
    {
      title: "Gross Profit",
      value: dashboard?.gross_profit ?? "0",
      change: dashboard?.gross_profit_change_pct ?? "0",
    },
    {
      title: "EBITDA",
      value: dashboard?.ebitda ?? "0",
      change: dashboard?.ebitda_change_pct ?? "0",
    },
    {
      title: "Net Profit",
      value: dashboard?.net_profit ?? "0",
      change: dashboard?.net_profit_change_pct ?? "0",
    },
  ]

  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => {
        const tone = changeTone(card.change)
        return (
          <article
            key={card.title}
            className="rounded-lg border border-border bg-card p-4"
          >
            <p className="text-sm text-muted-foreground">{card.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{scaleLabel}</p>
            <p className="mt-2 text-2xl font-semibold text-foreground">
              {fmt(card.value)}
            </p>
            <div className="mt-2 flex items-center gap-2 text-sm">
              {tone === "positive" ? (
                <ArrowUpRight className="h-4 w-4 text-[hsl(var(--brand-success))]" />
              ) : null}
              {tone === "negative" ? (
                <ArrowDownRight className="h-4 w-4 text-[hsl(var(--brand-danger))]" />
              ) : null}
              {tone === "neutral" ? (
                <Minus className="h-4 w-4 text-muted-foreground" />
              ) : null}
              <span
                className={
                  tone === "positive"
                    ? "text-[hsl(var(--brand-success))]"
                    : tone === "negative"
                    ? "text-[hsl(var(--brand-danger))]"
                    : "text-muted-foreground"
                }
              >
                {parsePercent(card.change).toFixed(2)}%
              </span>
            </div>
          </article>
        )
      })}
    </section>
  )
}
