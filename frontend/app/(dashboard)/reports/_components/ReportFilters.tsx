"use client"

import { cn } from "@/lib/utils"
import type { ActiveReportTab } from "../_hooks/useReports"

interface ReportFiltersProps {
  activeTab: ActiveReportTab
  onTabChange: (tab: ActiveReportTab) => void
}

export function ReportFilters({
  activeTab,
  onTabChange,
}: ReportFiltersProps) {
  return (
    <div className="flex items-center gap-2">
      {(["runs", "definitions"] as const).map((tab) => (
        <button
          key={tab}
          type="button"
          className={cn(
            "rounded-md border px-3 py-1.5 text-sm",
            activeTab === tab
              ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
          onClick={() => onTabChange(tab)}
        >
          {tab === "runs" ? "Runs" : "Definitions"}
        </button>
      ))}
    </div>
  )
}
