"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { type AuditorRequest } from "@/lib/types/sprint11"

export type PBCRequestTableProps = {
  rows: AuditorRequest[]
  onRespond?: (row: AuditorRequest, payload: {
    status: string
    response_notes?: string
    evidence_urls?: string[]
  }) => Promise<void>
}

export function PBCRequestTable({ rows, onRespond }: PBCRequestTableProps) {
  const [filterStatus, setFilterStatus] = useState<string>("")
  const filteredRows = useMemo(
    () => rows.filter((row) => (filterStatus ? row.status === filterStatus : true)),
    [rows, filterStatus],
  )

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <div className="border-b border-border px-3 py-2">
        <label className="text-xs text-muted-foreground">
          Filter:
          <select
            value={filterStatus}
            onChange={(event) => setFilterStatus(event.target.value)}
            className="ml-2 rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
          >
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="provided">Provided</option>
            <option value="partially_provided">Partially Provided</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
      </div>
      <table className="w-full min-w-[980px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">PBC#</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Category</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Description</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Status</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Due Date</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Action</th>
          </tr>
        </thead>
        <tbody>
          {filteredRows.map((row) => (
            <tr
              key={row.id}
              className={`border-b border-border/60 last:border-0 ${
                row.due_date && row.status !== "provided" && row.due_date < new Date().toISOString().slice(0, 10)
                  ? "bg-red-500/5"
                  : ""
              }`}
            >
              <td className="px-3 py-2 text-foreground">{row.request_number}</td>
              <td className="px-3 py-2 text-foreground">{row.category}</td>
              <td className="px-3 py-2 text-foreground">{row.description}</td>
              <td className="px-3 py-2 text-foreground">{row.status}</td>
              <td className="px-3 py-2 text-foreground">{row.due_date ?? "-"}</td>
              <td className="px-3 py-2">
                {onRespond ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      void onRespond(row, {
                        status: "provided",
                        response_notes: row.response_notes ?? "",
                        evidence_urls: row.evidence_urls,
                      })
                    }
                  >
                    Mark Provided
                  </Button>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
