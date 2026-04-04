import type { ReactNode } from "react"

export interface SortableHeaderProps {
  children: ReactNode
  sortKey: string
  currentSort: {
    key: string
    direction: "asc" | "desc" | null
  }
  onSort: (key: string) => void
  className?: string
}

export function SortableHeader({
  children,
  sortKey,
  currentSort,
  onSort,
  className,
}: SortableHeaderProps) {
  const isActive = currentSort.key === sortKey
  const ariaSortValue =
    isActive && currentSort.direction === "asc"
      ? "ascending"
      : isActive && currentSort.direction === "desc"
        ? "descending"
        : "none"

  return (
    <th scope="col" aria-sort={ariaSortValue} className={className}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="flex items-center gap-1 font-medium hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {children}
        <span aria-hidden="true" className="text-muted-foreground">
          {isActive ? (currentSort.direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  )
}
