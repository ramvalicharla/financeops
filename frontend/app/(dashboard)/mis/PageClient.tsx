"use client"

import { useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import dynamic from "next/dynamic"
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"
import { MISDashboard as MISDashboardCards } from "@/components/mis/MISDashboard"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { SortableHeader } from "@/components/ui/SortableHeader"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { useMISDashboard, useMISPeriods } from "@/hooks/useMIS"
import { useDisplayScale } from "@/lib/store/displayScale"
import { isZeroDecimal } from "@/lib/utils"
import type { MISLineItem } from "@/types/mis"

const MISLineChart = dynamic(
  () =>
    import("@/components/mis/MISLineChart").then(
      (module) => module.MISLineChart,
    ),
  {
    ssr: false,
    loading: () => <div className="h-64 w-full rounded-lg bg-muted" />,
  },
)

const currentMonth = new Date().toISOString().slice(0, 7)

export default function MISPage() {
  const { data: session } = useSession()
  const entityRoles = session?.user?.entity_roles ?? []
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null)
  const [selectedPeriod, setSelectedPeriod] = useState(currentMonth)
  const [sorting, setSorting] = useState<SortingState>([])

  const scale = useDisplayScale((state) => state.scale)
  const setScale = useDisplayScale((state) => state.setScale)
  const { fmtNum, scaleLabel } = useFormattedAmount()

  const periodsQuery = useMISPeriods(selectedEntityId)
  const dashboardQuery = useMISDashboard(selectedEntityId, selectedPeriod)

  const columns = useMemo<ColumnDef<MISLineItem>[]>(
    () => [
      {
        accessorKey: "label",
        header: "Line Item",
        cell: ({ row }) => (
          <div
            style={{ paddingLeft: `${row.original.indent_level * 16}px` }}
            className={row.original.is_heading ? "font-semibold text-foreground" : ""}
          >
            {row.original.label}
          </div>
        ),
      },
      {
        accessorKey: "current_value",
        header: "Current Period",
        cell: ({ row }) => (
          <div className="text-right">{fmtNum(row.original.current_value)}</div>
        ),
      },
      {
        accessorKey: "previous_value",
        header: "Previous Period",
        cell: ({ row }) => (
          <div className="text-right">{fmtNum(row.original.previous_value)}</div>
        ),
      },
      {
        accessorKey: "variance",
        header: "Variance",
        cell: ({ row }) =>
          row.original.is_heading ? (
            <span className="text-muted-foreground">-</span>
          ) : (
            <div
              className={`text-right ${
                row.original.variance.startsWith("-")
                  ? "text-[hsl(var(--brand-danger))]"
                  : isZeroDecimal(row.original.variance)
                  ? "text-muted-foreground"
                  : "text-[hsl(var(--brand-success))]"
              }`}
            >
              {fmtNum(row.original.variance)}
            </div>
          ),
      },
      {
        accessorKey: "variance_pct",
        header: "Variance %",
        cell: ({ row }) =>
          row.original.is_heading ? (
            <span className="text-muted-foreground">-</span>
          ) : (
            <div
              className={`text-right ${
                row.original.variance_pct.startsWith("-")
                  ? "text-[hsl(var(--brand-danger))]"
                  : row.original.variance_pct === "0"
                  ? "text-muted-foreground"
                  : "text-[hsl(var(--brand-success))]"
              }`}
            >
              {row.original.variance_pct}%
            </div>
          ),
      },
    ],
    [fmtNum],
  )

  const table = useReactTable({
    data: dashboardQuery.data?.line_items ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const currentSort = {
    key: sorting[0]?.id ?? "",
    direction: sorting[0]?.desc === undefined ? null : sorting[0].desc ? "desc" : "asc",
  } as const

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="mb-3 flex items-center justify-end">
          <ScaleSelector value={scale} onChange={setScale} />
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="mis-entity">
              Entity
            </label>
            <select
              id="mis-entity"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={selectedEntityId ?? ""}
              onChange={(event) => setSelectedEntityId(event.target.value || null)}
            >
              <option value="">Select entity</option>
              {entityRoles.map((entityRole) => (
                <option key={entityRole.entity_id} value={entityRole.entity_id}>
                  {entityRole.entity_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="mis-period">
              Period
            </label>
            <select
              id="mis-period"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={selectedPeriod}
              onChange={(event) => setSelectedPeriod(event.target.value)}
            >
              {[...(periodsQuery.data ?? [{ period: currentMonth, label: currentMonth }])].map(
                (period) => (
                  <option key={period.period} value={period.period}>
                    {period.label}
                  </option>
                ),
              )}
            </select>
          </div>
        </div>
      </section>

      <MISDashboardCards dashboard={dashboardQuery.data ?? null} />

      {dashboardQuery.isLoading ? (
        <div className="h-48 w-full rounded-lg bg-muted" />
      ) : null}

      {dashboardQuery.isSuccess ? (
        <div className="h-3 w-3 animate-pulse rounded-full bg-muted" />
      ) : null}

      {dashboardQuery.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load MIS dashboard data.
        </p>
      ) : null}

      <MISLineChart data={dashboardQuery.data?.chart_data ?? []} />

      <section className="rounded-lg border border-border bg-card p-4">
        <h3 className="mb-1 text-lg font-semibold text-foreground">MIS Detail</h3>
        <p className="mb-3 text-xs text-muted-foreground">{scaleLabel}</p>
        <div className="overflow-x-auto rounded-md border border-border">
          <table aria-label="Management information" className="w-full min-w-[860px] text-sm">
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
      </section>
    </div>
  )
}
