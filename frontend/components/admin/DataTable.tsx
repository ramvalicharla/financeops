"use client"

import type { ReactNode } from "react"

export type DataTableColumn<T> = {
  key: string
  header: string
  className?: string
  render: (row: T) => ReactNode
}

export function DataTable<T>({
  columns,
  rows,
  emptyMessage = "No data found.",
}: {
  columns: DataTableColumn<T>[]
  rows: T[]
  emptyMessage?: string
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-background/50 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={`px-4 py-3 text-left ${column.className ?? ""}`}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {rows.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td key={column.key} className={`px-4 py-3 ${column.className ?? ""}`}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-6 text-center text-sm text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
