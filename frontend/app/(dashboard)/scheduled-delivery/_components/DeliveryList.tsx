"use client"

import { Loader2, Play, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { DeliveryScheduleResponse } from "@/lib/types/scheduled-delivery"
import { cn } from "@/lib/utils"
import { formatDateTime } from "../_hooks/useDeliveries"

interface DeliveryListProps {
  definitionNameById: Map<string, string>
  loading: boolean
  runningId: string | null
  schedules: DeliveryScheduleResponse[]
  onDelete: (scheduleId: string) => void
  onEdit: (schedule: DeliveryScheduleResponse) => void
  onTrigger: (scheduleId: string) => void
}

const statusBadge = (isActive: boolean): string =>
  isActive
    ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
    : "bg-muted text-muted-foreground"

export function DeliveryList({
  definitionNameById,
  loading,
  runningId,
  schedules,
  onDelete,
  onEdit,
  onTrigger,
}: DeliveryListProps) {
  return (
    <section className="rounded-lg border border-border bg-card p-4">
      {loading ? (
        <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
      ) : null}
      {!loading && !schedules.length ? (
        <p className="rounded-md border border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
          No delivery schedules yet.
        </p>
      ) : null}
      {!!schedules.length ? (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[1020px] text-sm">
            <thead>
              <tr className="bg-muted/30">
                <th className="px-3 py-2 text-left font-medium text-foreground">Name</th>
                <th className="px-3 py-2 text-left font-medium text-foreground">Type</th>
                <th className="px-3 py-2 text-left font-medium text-foreground">Source</th>
                <th className="px-3 py-2 text-left font-medium text-foreground">Cron</th>
                <th className="px-3 py-2 text-left font-medium text-foreground">
                  Next Run
                </th>
                <th className="px-3 py-2 text-left font-medium text-foreground">
                  Active
                </th>
                <th className="px-3 py-2 text-left font-medium text-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((schedule) => (
                <tr key={schedule.id} className="border-t border-border">
                  <td className="px-3 py-2 text-muted-foreground">{schedule.name}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {schedule.schedule_type}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {definitionNameById.get(schedule.source_definition_id) ??
                      schedule.source_definition_id}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {schedule.cron_expression}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {formatDateTime(schedule.next_run_at)}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                        statusBadge(schedule.is_active),
                      )}
                    >
                      {schedule.is_active ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!schedule.is_active || runningId === schedule.id}
                        onClick={() => onTrigger(schedule.id)}
                      >
                        {runningId === schedule.id ? (
                          <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="mr-1 h-3.5 w-3.5" />
                        )}
                        Trigger Now
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onEdit(schedule)}
                      >
                        Edit
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onDelete(schedule.id)}
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
