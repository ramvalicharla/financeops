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
import { formatINR } from "@/lib/utils"
import type { BillingInvoice } from "@/types/billing"

interface InvoiceTableProps {
  invoices: BillingInvoice[]
}

const statusClass: Record<BillingInvoice["status"], string> = {
  draft: "bg-muted text-muted-foreground",
  open: "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]",
  paid: "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  void: "bg-muted text-muted-foreground",
  uncollectible: "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
}

export function InvoiceTable({ invoices }: InvoiceTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = useMemo<ColumnDef<BillingInvoice>[]>(
    () => [
      {
        accessorKey: "provider_invoice_id",
        header: "Invoice #",
      },
      {
        id: "period",
        header: "Period",
        cell: ({ row }) => {
          const date = new Date(row.original.created_at)
          return date.toLocaleString("en-IN", { month: "short", year: "numeric" })
        },
      },
      {
        accessorKey: "total",
        header: "Amount",
        cell: ({ row }) => (
          <div className="text-right">{formatINR(row.original.total)}</div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <span
            className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusClass[row.original.status]}`}
          >
            {row.original.status}
          </span>
        ),
      },
      {
        accessorKey: "created_at",
        header: "Date",
        cell: ({ row }) => new Date(row.original.created_at).toLocaleDateString(),
      },
      {
        id: "download",
        header: "Download",
        cell: ({ row }) => (
          <Button
            size="sm"
            type="button"
            variant="outline"
            disabled={!row.original.invoice_pdf_url}
            onClick={() => {
              if (!row.original.invoice_pdf_url) {
                return
              }
              window.open(row.original.invoice_pdf_url, "_blank", "noopener,noreferrer")
            }}
          >
            Download
          </Button>
        ),
      },
    ],
    [],
  )

  const table = useReactTable({
    data: invoices,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: {
        pageSize: 10,
      },
    },
  })

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[840px] text-sm">
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
              <tr key={row.id} className="border-t border-border">
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
