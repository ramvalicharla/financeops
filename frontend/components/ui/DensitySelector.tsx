"use client"

import * as React from "react"
import { LayoutList, LayoutGrid } from "lucide-react"
import { useUIStore } from "@/lib/store/ui"
import { cn } from "@/lib/utils"

export function DensitySelector({ className }: { className?: string }) {
  const density = useUIStore((state) => state.density)
  const setDensity = useUIStore((state) => state.setDensity)

  return (
    <div className={cn("flex items-center gap-1 rounded-md border border-border p-1 bg-card", className)}>
      <button
        type="button"
        onClick={() => setDensity("comfortable")}
        className={cn(
          "flex items-center justify-center rounded px-2 py-1 transition-colors hover:text-foreground",
          density === "comfortable"
            ? "bg-muted text-foreground shadow-sm"
            : "text-muted-foreground",
        )}
        title="Comfortable Density"
      >
        <LayoutGrid className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => setDensity("compact")}
        className={cn(
          "flex items-center justify-center rounded px-2 py-1 transition-colors hover:text-foreground",
          density === "compact"
            ? "bg-muted text-foreground shadow-sm"
            : "text-muted-foreground",
        )}
        title="Compact Density"
      >
        <LayoutList className="h-4 w-4" />
      </button>
    </div>
  )
}
