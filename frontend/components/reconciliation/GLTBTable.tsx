"use client"

import { useMemo, useState } from "react"
import type { CSSProperties } from "react"
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type Column,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"
import { VarianceBadge } from "@/components/reconciliation/VarianceBadge"
import { SortableHeader } from "@/components/ui/SortableHeader"
import { Button } from "@/components/ui/button"
import { PaginationBar } from "@/components/ui/PaginationBar"
import { formatINR, isZeroDecimal } from "@/lib/utils"
import type { GLTBAccount } from "@/types/reconciliation"

interface GLTBTableProps {
  accounts: GLTBAccount[]
  onRowClick: (account: GLTBAccount) => void
  onSelectionChange?: (ids: Set<string>) => void
  selectedIds?: Set<string>
}

export function GLTBTable({ accounts, onRowClick, onSelectionChange, selectedIds = new Set() }: GLTBTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = useMemo<ColumnDef<GLTBAccount>[]>(
    () => [
      {
        accessorKey: "account_code",
        header: "Account Code",
      },
      {
        accessorKey: "account_name",
        header: "Account Name",
      },
      {
        accessorKey: "account_type",
        header: "Type",
      },
      {
        accessorKey: "tb_balance",
        header: "TB Balance",
        cell: ({ row }) => (
          <div className="text-right">{formatINR(row.original.tb_balance)}</div>
        ),
      },
      {
        accessorKey: "gl_balance",
        header: "GL Balance",
        cell: ({ row }) => (
          <div className="text-right">{formatINR(row.original.gl_balance)}</div>
        ),
      },
      {
        accessorKey: "variance",
        header: "Variance",
        cell: ({ row }) => (
          <div
            className={`text-right ${
              isZeroDecimal(row.original.variance)
                ? "text-[hsl(var(--brand-success))]"
                : "text-[hsl(var(--brand-danger))]"
            }`}
          >
            {formatINR(row.original.variance)}
          </div>
        ),
      },
      {
        accessorKey: "variance_pct",
        header: "Variance %",
        cell: ({ row }) => (
          <div className="text-right text-muted-foreground">
            {row.original.variance_pct}%
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <VarianceBadge status={row.original.status} />,
      },
    ],
    [],
  )

  const table = useReactTable({
    data: accounts,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      columnPinning: { left: ["account_code"] },
      pagination: {
        pageSize: 50,
      },
    },
  })

  function getPinStyles(column: Column<GLTBAccount>): CSSProperties {
    const isPinned = column.getIsPinned()
    if (!isPinned) return {}
    return {
      position: "sticky",
      left: column.getStart("left"),
      zIndex: 1,
      background: "hsl(var(--background))",
    }
  }

  const currentSort = {
    key: sorting[0]?.id ?? "",
    direction: sorting[0]?.desc === undefined ? null : sorting[0].desc ? "desc" : "asc",
  } as const

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table aria-label="General ledger and trial balance" className="w-full min-w-[980px] text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="bg-muted/30">
                {onSelectionChange && (
                  <th className="px-3 py-2 text-left w-[40px] sticky left-0 z-10 bg-muted/30">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={accounts.length > 0 && Array.from(accounts).every(a => selectedIds.has(a.account_code))}
                      onChange={(e) => {
                        if (e.target.checked) {
                          onSelectionChange(new Set(accounts.map(a => a.account_code)))
                        } else {
                          onSelectionChange(new Set())
                        }
                      }}
                    />
                  </th>
                )}
                {headerGroup.headers.map((header) =>
                  header.isPlaceholder ? null : (
                    <SortableHeader
                      key={header.id}
                      sortKey={header.column.id}
                      currentSort={currentSort}
                      onSort={(key) => {
                        table.getColumn(key)?.toggleSorting()
                      }}
                      className="px-3 py-2 text-left text-foreground"
                      style={getPinStyles(header.column)}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                    </SortableHeader>
                  ),
                )}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                role="row"
                tabIndex={0}
                className="cursor-pointer border-t border-border hover:bg-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                onClick={() => onRowClick(row.original)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onRowClick(row.original)
                  }
                }}
                aria-label={`View details for ${row.original.account_name || row.original.account_code}`}
              >
                {onSelectionChange && (
                  <td className="px-3 py-2 sticky left-0 z-10 bg-card">
                    <input
                      type="checkbox"
                      className="rounded border-border"
                      checked={selectedIds.has(row.original.account_code)}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => {
                        const next = new Set(selectedIds)
                        if (e.target.checked) next.add(row.original.account_code)
                        else next.delete(row.original.account_code)
                        onSelectionChange(next)
                      }}
                    />
                  </td>
                )}
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="px-3 py-2 text-muted-foreground"
                    style={getPinStyles(cell.column)}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationBar
        total={table.getPrePaginationRowModel().rows.length}
        skip={table.getState().pagination.pageIndex * table.getState().pagination.pageSize}
        limit={table.getState().pagination.pageSize}
        onPageChange={(skip) => table.setPageIndex(Math.floor(skip / table.getState().pagination.pageSize))}
        hasMore={table.getCanNextPage()}
      />
    </div>
  )
}
