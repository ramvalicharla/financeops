import { Clock3 } from "lucide-react"
import type { ServiceRegistryTask } from "@/lib/types/service-registry"

type TaskRegistryTableProps = {
  tasks: ServiceRegistryTask[]
}

const statusClass = (status: ServiceRegistryTask["last_run_status"]): string => {
  if (status === "success") return "text-[hsl(var(--brand-success))]"
  if (status === "failure") return "text-[hsl(var(--brand-danger))]"
  if (status === "timeout") return "text-[hsl(var(--brand-warning))]"
  return "text-muted-foreground"
}

export function TaskRegistryTable({ tasks }: TaskRegistryTableProps) {
  if (tasks.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card px-4 py-6 text-sm text-muted-foreground">
        No registered tasks found yet.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table aria-label="Task registry" className="min-w-full text-sm">
        <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2">Task Name</th>
            <th scope="col" className="px-3 py-2">Queue</th>
            <th scope="col" className="px-3 py-2">Last Run</th>
            <th scope="col" className="px-3 py-2">Status</th>
            <th scope="col" className="px-3 py-2">Avg Duration</th>
            <th scope="col" className="px-3 py-2">Success Rate</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id} className="border-b border-border/50 align-top">
              <td className="px-3 py-2">
                <div className="flex items-center gap-1">
                  <span>{task.task_name}</span>
                  {task.is_scheduled ? <Clock3 className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                </div>
              </td>
              <td className="px-3 py-2">{task.queue_name}</td>
              <td className="px-3 py-2">{task.last_run_at ?? "-"}</td>
              <td className={`px-3 py-2 ${statusClass(task.last_run_status)}`}>
                {task.last_run_status ?? "unknown"}
              </td>
              <td className="px-3 py-2">
                {task.avg_duration_seconds ? `${task.avg_duration_seconds}s` : "-"}
              </td>
              <td className="px-3 py-2">
                {task.success_rate_7d ? `${(Number(task.success_rate_7d) * 100).toFixed(2)}%` : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
