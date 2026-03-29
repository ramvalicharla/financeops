"use client"

import type { ReactNode } from "react"
import {
  AlertTriangle,
  BriefcaseBusiness,
  Building2,
  CalendarCheck2,
  FileText,
  FolderKanban,
  HandCoins,
  Landmark,
  Receipt,
  Search,
  Shapes,
} from "lucide-react"
import { cn } from "@/lib/utils"
import type { SearchResultRow } from "@/lib/types/search"

type SearchResultProps = {
  result: SearchResultRow
  isActive: boolean
  query: string
  onSelect: (result: SearchResultRow) => void
}

const entityIcon = (entityType: string) => {
  switch (entityType) {
    case "expense_claim":
      return Receipt
    case "anomaly":
      return AlertTriangle
    case "checklist_task":
      return CalendarCheck2
    case "fdd_engagement":
    case "ppa_engagement":
    case "ma_workspace":
      return BriefcaseBusiness
    case "marketplace_template":
      return Shapes
    case "mis_line":
      return Landmark
    case "document":
      return FileText
    case "closing_run":
      return FolderKanban
    case "budget_line":
    case "forecast_run":
      return HandCoins
    default:
      return Search
  }
}

const highlight = (value: string, query: string): ReactNode => {
  const needle = query.trim()
  if (!needle || needle.length < 2) {
    return value
  }
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const pattern = new RegExp(`(${escaped})`, "ig")
  const parts = value.split(pattern)
  return parts.map((part, index) =>
    index % 2 === 1 ? (
      <mark key={`${part}-${index}`} className="bg-[hsl(var(--brand-primary)/0.25)] text-foreground">
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  )
}

export function SearchResult({ result, isActive, query, onSelect }: SearchResultProps) {
  const Icon = entityIcon(result.entity_type)
  const entityLabel = result.entity_type.replaceAll("_", " ")

  return (
    <button
      type="button"
      onClick={() => onSelect(result)}
      className={cn(
        "flex w-full items-start gap-3 rounded-md border border-transparent px-3 py-2 text-left transition",
        isActive
          ? "border-[hsl(var(--brand-primary)/0.5)] bg-[hsl(var(--brand-primary)/0.16)]"
          : "hover:bg-accent",
      )}
    >
      <span className="mt-0.5 rounded-md border border-border bg-background p-1.5 text-muted-foreground">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">
          {highlight(result.title, query)}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {result.subtitle ? highlight(result.subtitle, query) : "No subtitle"}
        </span>
      </span>
      <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {entityLabel}
      </span>
    </button>
  )
}
