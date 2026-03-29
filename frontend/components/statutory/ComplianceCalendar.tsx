"use client"

import { type StatutoryCalendarItem } from "@/lib/types/sprint11"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type ComplianceItem = {
  filing: StatutoryCalendarItem
  onMarkFiled?: (filingId: string) => Promise<void>
}

export type ComplianceCalendarProps = {
  items: StatutoryCalendarItem[]
  onMarkFiled?: (filingId: string) => Promise<void>
}

function FilingItem({ filing, onMarkFiled }: ComplianceItem) {
  const daysUntil = filing.days_until_due
  const isOverdue = filing.is_overdue

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border p-4",
        isOverdue && "border-red-500/40 bg-red-500/5",
        !isOverdue && daysUntil <= 30 && "border-amber-500/40 bg-amber-500/5",
        !isOverdue && daysUntil > 30 && filing.status === "filed" && "border-green-500/40 bg-green-500/5",
        !isOverdue && daysUntil > 30 && filing.status === "pending" && "border-gray-700 bg-gray-800/50",
      )}
    >
      <div className="w-20 text-center">
        <p className="text-xs text-gray-400">
          {isOverdue ? `${Math.abs(daysUntil)}d overdue` : `${daysUntil}d left`}
        </p>
      </div>
      <div className="flex-1">
        <p className="font-medium text-white">{filing.form_number}</p>
        <p className="text-sm text-gray-400">{filing.form_description}</p>
        <p className="text-xs text-gray-500">Due: {filing.due_date}</p>
      </div>
      <span
        className={cn(
          "rounded-full border px-2 py-0.5 text-xs",
          filing.status === "filed" && "border-green-500/40 text-green-400",
          filing.status === "pending" && "border-blue-500/40 text-blue-400",
          filing.status === "overdue" && "border-red-500/40 text-red-400",
          filing.status === "exempt" && "border-gray-500/40 text-gray-300",
        )}
      >
        {filing.status}
      </span>
      {filing.status === "pending" && onMarkFiled ? (
        <Button variant="outline" size="sm" onClick={() => void onMarkFiled(filing.id)}>
          Mark as Filed
        </Button>
      ) : null}
    </div>
  )
}

export function ComplianceCalendar({ items, onMarkFiled }: ComplianceCalendarProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Compliance Calendar</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <FilingItem key={item.id} filing={item} onMarkFiled={onMarkFiled} />
        ))}
      </div>
    </div>
  )
}
