"use client"

import { useMemo, useState } from "react"
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"
import { SortableHeader } from "@/components/ui/SortableHeader"
import { PaginationBar } from "@/components/ui/PaginationBar"
import { formatINR, isZeroDecimal } from "@/lib/utils"
import type { PayrollCostCentre } from "@/types/reconciliation"

interface PayrollReconTableProps {
  costCentres: PayrollCostCentre[]
  onRowClick: (costCentre: PayrollCostCentre) => void
}

export function PayrollReconTable({
  costCentres,
  onRowClick,
}: PayrollReconTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = useMemo<ColumnDef<PayrollCostCentre>[]>(
    () => [
      {
        accessorKey: "cost_centre_name",
        header: "Cost Centre",
      },
      {
        accessorKey: "payroll_amount",
        header: "Payroll Amount",
        cell: ({ row }) => (
          <div className="text-right">{formatINR(row.original.payroll_amount)}</div>
        ),
      },
      {
        accessorKey: "gl_amount",
        header: "GL Amount",
        cell: ({ row }) => (
          <div className="text-right">{formatINR(row.original.gl_amount)}</div>
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
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <span
            className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
              row.original.status === "MATCHED"
                ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
                : "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
            }`}
          >
            {row.original.status === "MATCHED" ? "Matched" : "Variance"}
          </span>
        ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: costCentres,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 20,
      },
    },
  })

  const currentSort = {
    key: sorting[0]?.id ?? "",
    direction: sorting[0]?.desc === undefined ? null : sorting[0].desc ? "desc" : "asc",
  } as const

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto w-full rounded-md border border-border">
        <table role="grid" aria-rowcount={costCentres.length} aria-label="Payroll reconciliation" className="w-full min-w-[760px] text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="bg-muted/30">
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
                  if (event.key === "ArrowDown") {
                    event.preventDefault()
                    const nextRow = event.currentTarget.nextElementSibling as HTMLElement
                    if (nextRow) nextRow.focus()
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault()
                    const prevRow = event.currentTarget.previousElementSibling as HTMLElement
                    if (prevRow) prevRow.focus()
                  } else if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    onRowClick(row.original)
                  }
                }}
                aria-label={`View details for ${row.original.cost_centre_name}`}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-3 py-2 text-muted-foreground">
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
