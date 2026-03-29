"use client"

import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { CovenantGauge } from "@/components/covenants/CovenantGauge"

export type CovenantCardProps = {
  facilityName: string
  covenantLabel: string
  covenantType: string
  threshold: string
  actual: string
  direction: "above" | "below"
  status: "pass" | "near_breach" | "breach"
  headroomPct: string
  trend: "improving" | "stable" | "worsening"
}

const statusLabel: Record<CovenantCardProps["status"], string> = {
  pass: "Pass",
  near_breach: "Near Breach",
  breach: "Breach",
}

const isRatioCovenantType = (covenantType: string, covenantLabel: string): boolean => {
  const text = `${covenantType} ${covenantLabel}`.toLowerCase()
  return (
    text.includes("ratio")
    || text.includes("dscr")
    || text.includes("icr")
    || text.includes("debt/ebitda")
    || text.includes("debt to ebitda")
  )
}

export function CovenantCard({
  facilityName,
  covenantLabel,
  covenantType,
  threshold,
  actual,
  direction,
  status,
  headroomPct,
  trend,
}: CovenantCardProps) {
  const { fmtRatio, fmt } = useFormattedAmount()
  const actualValue = Number.parseFloat(actual)
  const thresholdValue = Number.parseFloat(threshold)

  const ratioType = isRatioCovenantType(covenantType, covenantLabel)
  const actualLabel = ratioType ? fmtRatio(actual) : fmt(actual)
  const thresholdLabel = ratioType ? fmtRatio(threshold) : fmt(threshold)

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">{facilityName}</p>
      <p className="text-xs text-muted-foreground">{covenantLabel}</p>
      <p className="text-xs text-muted-foreground">{covenantType} ({direction})</p>
      <div className="mt-3 flex justify-center">
        <CovenantGauge
          actual={Number.isNaN(actualValue) ? 0 : actualValue}
          threshold={Number.isNaN(thresholdValue) ? 0 : thresholdValue}
          direction={direction}
          status={status}
          actualLabel={actualLabel}
          thresholdLabel={thresholdLabel}
        />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Headroom</span>
        <span className="text-foreground">{headroomPct}%</span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Status</span>
        <span
          className={
            status === "pass"
              ? "text-emerald-400"
              : status === "near_breach"
                ? "text-amber-400"
                : "text-red-400"
          }
        >
          {statusLabel[status]}
        </span>
      </div>
      <div className="mt-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Trend</span>
        <span className="text-foreground">{trend}</span>
      </div>
    </div>
  )
}
