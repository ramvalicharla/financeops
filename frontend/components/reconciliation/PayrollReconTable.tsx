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
import { Button } from "@/components/ui/button"
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

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="bg-muted/30">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="cursor-pointer px-3 py-2 text-left font-medium text-foreground"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="cursor-pointer border-t border-border hover:bg-accent/30"
                onClick={() => onRowClick(row.original)}
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
      <div className="flex items-center justify-between text-sm">
        <p className="text-muted-foreground">
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {table.getPageCount() || 1}
        </p>
        <div className="flex gap-2">
          <Button
            size="sm"
            type="button"
            variant="outline"
            disabled={!table.getCanPreviousPage()}
            onClick={() => table.previousPage()}
          >
            Previous
          </Button>
          <Button
            size="sm"
            type="button"
            variant="outline"
            disabled={!table.getCanNextPage()}
            onClick={() => table.nextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
