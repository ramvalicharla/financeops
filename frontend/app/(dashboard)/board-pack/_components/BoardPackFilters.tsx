"use client"

import { cn } from "@/lib/utils"
import type { ActiveBoardPackTab } from "../_hooks/useBoardPack"

interface BoardPackFiltersProps {
  activeTab: ActiveBoardPackTab
  onTabChange: (tab: ActiveBoardPackTab) => void
}

export function BoardPackFilters({
  activeTab,
  onTabChange,
}: BoardPackFiltersProps) {
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
