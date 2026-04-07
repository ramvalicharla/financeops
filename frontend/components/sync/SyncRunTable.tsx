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
import { formatDistanceToNowStrict } from "date-fns"
import { SortableHeader } from "@/components/ui/SortableHeader"
import { Button } from "@/components/ui/button"
import { SyncStatusBadge } from "@/components/sync/SyncStatusBadge"
import { cn } from "@/lib/utils"
import type { SyncRun } from "@/types/sync"

interface SyncRunTableProps {
  runs: SyncRun[]
  onValidationReport: (run: SyncRun) => void
  onApprovePublish: (run: SyncRun) => void
  onViewDrift: (run: SyncRun) => void
  isApproving: boolean
  canApprovePublish: boolean
  approvePublishTitle?: string
}

const formatRelative = (value: string): string =>
  formatDistanceToNowStrict(new Date(value), { addSuffix: true })

const driftBadgeClass = (severity: SyncRun["drift_severity"]): string => {
  if (severity === "CRITICAL") {
    return "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
  }
  if (severity === "SIGNIFICANT") {
    return "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]"
  }
  if (severity === "MINOR") {
    return "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
  }
  return "bg-muted text-muted-foreground"
}

export function SyncRunTable({
  runs,
  onValidationReport,
  onApprovePublish,
  onViewDrift,
  isApproving,
  canApprovePublish,
  approvePublishTitle,
}: SyncRunTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "started_at", desc: true },
  ])

  const columns = useMemo<ColumnDef<SyncRun>[]>(
    () => [
      {
        accessorKey: "dataset_type",
        header: "Dataset Type",
        cell: ({ row }) => row.original.dataset_type.replaceAll("_", " "),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <SyncStatusBadge status={row.original.status} />,
      },
      {
        accessorKey: "started_at",
        header: "Started",
        cell: ({ row }) => formatRelative(row.original.started_at),
      },
      {
        accessorKey: "duration_seconds",
        header: "Duration",
        cell: ({ row }) =>
          row.original.duration_seconds !== null
            ? `${row.original.duration_seconds}s`
            : "-",
      },
      {
        accessorKey: "records_extracted",
        header: "Records",
        cell: ({ row }) => row.original.records_extracted ?? "-",
      },
      {
        accessorKey: "drift_severity",
        header: "Drift",
        cell: ({ row }) => (
          <span
            className={cn(
              "inline-flex rounded-full px-2 py-1 text-xs font-medium",
              driftBadgeClass(row.original.drift_severity),
            )}
          >
            {row.original.drift_severity ?? "NONE"}
          </span>
        ),
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          const run = row.original
          return (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => onValidationReport(run)}
                type="button"
              >
                Validation Report
              </Button>
              {run.status === "COMPLETED" && run.publish_event_id ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={isApproving || !canApprovePublish}
                  title={!canApprovePublish ? approvePublishTitle : undefined}
                  onClick={() => onApprovePublish(run)}
                  type="button"
                >
                  Approve Publish
                </Button>
              ) : null}
              {run.drift_severity && run.drift_severity !== "NONE" ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onViewDrift(run)}
                  type="button"
                >
                  View Drift
                </Button>
              ) : null}
            </div>
          )
        },
      },
    ],
    [approvePublishTitle, canApprovePublish, isApproving, onApprovePublish, onValidationReport, onViewDrift],
  )

  const table = useReactTable({
    data: runs,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
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
      <div className="overflow-x-auto rounded-md border border-border">
        <table aria-label="Sync runs" className="w-full min-w-[980px] border-collapse text-sm">
          <thead className="bg-muted/30">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) =>
                  header.isPlaceholder ? null : header.column.getCanSort() ? (
                    <SortableHeader
                      key={header.id}
                      sortKey={header.column.id}
                      currentSort={currentSort}
                      onSort={(key) => {
                        table.getColumn(key)?.toggleSorting()
                      }}
                      className="border-b border-border px-3 py-2 text-left text-foreground"
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                    </SortableHeader>
                  ) : (
                    <th
                      key={header.id}
                      scope="col"
                      className="border-b border-border px-3 py-2 text-left font-medium text-foreground"
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                    </th>
                  ),
                )}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-b border-border/60">
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
            variant="outline"
            disabled={!table.getCanPreviousPage()}
            onClick={() => table.previousPage()}
            type="button"
          >
            Previous
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!table.getCanNextPage()}
            onClick={() => table.nextPage()}
            type="button"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
