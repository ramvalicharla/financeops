"use client"

import type { ReactNode } from "react"
import { PaginationBar, type PaginationBarProps } from "@/components/ui/PaginationBar"

export type DataTableColumn<T> = {
  key: string
  header: ReactNode
  className?: string
  render: (row: T) => ReactNode
}

export function DataTable<T>({
  columns,
  rows,
  emptyMessage = "No data found.",
  label = "Data table",
  selectable,
  getRowId,
  selectedIds = new Set<string>(),
  onSelectionChange,
  pagination,
}: {
  columns: DataTableColumn<T>[]
  rows: T[]
  emptyMessage?: string
  label?: string
  selectable?: boolean
  getRowId?: (row: T) => string
  selectedIds?: Set<string>
  onSelectionChange?: (ids: Set<string>) => void
  pagination?: Omit<PaginationBarProps, "total"> & { total?: number }
}) {
  const isAllSelected = rows.length > 0 && Array.from(rows).every(r => selectedIds.has(getRowId?.(r) ?? ""))

  const handleSelectAll = () => {
    if (!onSelectionChange || !getRowId) return
    if (isAllSelected) {
      onSelectionChange(new Set())
    } else {
      const allIds = new Set(rows.map(getRowId))
      onSelectionChange(allIds)
    }
  }

  const handleSelectOne = (id: string) => {
    if (!onSelectionChange) return
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    onSelectionChange(next)
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table aria-label={label} className="min-w-full text-sm">
          <thead className="bg-background/50 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              {selectable && (
                <th scope="col" className="px-4 py-3 text-left w-[40px]">
                  <input
                    type="checkbox"
                    className="rounded border-border"
                    checked={isAllSelected}
                    onChange={handleSelectAll}
                  />
                </th>
              )}
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`px-4 py-3 text-left ${column.className ?? ""}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {rows.map((row, index) => {
              const rowId = getRowId?.(row) ?? String(index)
              const isSelected = selectedIds.has(rowId)
              return (
              <tr key={index} className={isSelected ? "bg-primary/5" : ""}>
                {selectable && (
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={isSelected}
                      onChange={() => handleSelectOne(rowId)}
                    />
                  </td>
                )}
                {columns.map((column) => (
                  <td key={column.key} className={`px-4 py-3 ${column.className ?? ""}`}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
              )
            })}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {pagination && (
        <PaginationBar
          total={pagination.total ?? 0}
          skip={pagination.skip}
          limit={pagination.limit}
          onPageChange={pagination.onPageChange}
          hasMore={pagination.hasMore}
        />
      )}
    </div>
  )
}
