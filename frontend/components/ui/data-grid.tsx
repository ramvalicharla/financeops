"use client"

import * as React from "react"
import {
  type ColumnDef,
  getCoreRowModel,
  useReactTable,
  flexRender,
  type SortingState,
  getSortedRowModel,
} from "@tanstack/react-table"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"

import { useUIStore } from "@/lib/store/ui"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataGridProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  enableMultiSort?: boolean
}

export function DataGrid<TData, TValue>({
  columns,
  data,
  enableMultiSort = true,
}: DataGridProps<TData, TValue>) {
  const density = useUIStore((state) => state.density)
  const [sorting, setSorting] = React.useState<SortingState>([])

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    enableMultiSort: enableMultiSort,
    state: {
      sorting,
    },
  })

  return (
    <div className="rounded-md border border-border shadow-sm overflow-hidden bg-card">
      <Table>
        <TableHeader className="bg-muted/50 border-b border-border shadow-sm">
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id} className="hover:bg-transparent">
              {headerGroup.headers.map((header) => {
                const isSortable = header.column.getCanSort()
                return (
                  <TableHead 
                    key={header.id} 
                    className={isSortable ? "cursor-pointer select-none group" : ""}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-2">
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                      {/* Excel-style Sort Indicators */}
                      {isSortable && (
                        <span className="w-4 h-4 ml-1 flex items-center justify-center opacity-50 group-hover:opacity-100 transition-opacity">
                          {{
                            asc: <ArrowUp className="w-3 h-3" />,
                            desc: <ArrowDown className="w-3 h-3" />,
                          }[header.column.getIsSorted() as string] ?? (
                            <ArrowUpDown className="w-3 h-3 text-muted-foreground/30" />
                          )}
                        </span>
                      )}
                    </div>
                  </TableHead>
                )
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows?.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                data-state={row.getIsSelected() && "selected"}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell 
                    key={cell.id} 
                    className={density === "compact" ? "py-1 px-3 text-xs" : "py-2.5 px-3"}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                No data available in ledger.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
