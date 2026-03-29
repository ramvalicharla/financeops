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
import { VarianceBadge } from "@/components/reconciliation/VarianceBadge"
import { Button } from "@/components/ui/button"
import { formatINR, isZeroDecimal } from "@/lib/utils"
import type { GLTBAccount } from "@/types/reconciliation"

interface GLTBTableProps {
  accounts: GLTBAccount[]
  onRowClick: (account: GLTBAccount) => void
}

export function GLTBTable({ accounts, onRowClick }: GLTBTableProps) {
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
      pagination: {
        pageSize: 50,
      },
    },
  })

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[980px] text-sm">
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
