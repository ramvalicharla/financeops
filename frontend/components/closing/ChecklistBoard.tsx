"use client"

import { Clock3, Lock, Sparkles, UserCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ChecklistTaskItem } from "@/lib/types/closing"
import { cn } from "@/lib/utils"

interface ChecklistBoardProps {
  tasks: ChecklistTaskItem[]
  loading: boolean
  readOnly: boolean
  onOpenTask: (task: ChecklistTaskItem) => void
}

function TaskCard({ task, readOnly, onOpenTask }: { task: ChecklistTaskItem; readOnly: boolean; onOpenTask: (task: ChecklistTaskItem) => void }) {
  const overdue = Boolean(task.due_date && task.status !== "completed" && task.status !== "skipped" && task.due_date < new Date().toISOString().slice(0, 10))

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card/70 p-3",
        overdue ? "border-[hsl(var(--brand-danger))]" : "",
      )}
      data-testid="checklist-task-card"
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{task.task_name}</p>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">{task.status}</span>
      </div>
      <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><UserCircle2 className="h-3.5 w-3.5" />{task.assigned_to ? "Assigned" : "Unassigned"}</span>
        <span className="flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />{task.due_date ?? "No due date"}</span>
        {overdue ? (
          <span className="col-span-2 text-[hsl(var(--brand-danger))]" data-testid="overdue-indicator">
            Overdue
          </span>
        ) : null}
        {!task.dependency_met ? (
          <span className="col-span-2 flex items-center gap-1 text-amber-300"><Lock className="h-3.5 w-3.5" />Blocked by dependency</span>
        ) : null}
        {task.is_auto_completed ? (
          <span className="col-span-2 flex items-center gap-1 text-emerald-300" data-testid="autocompleted-badge">
            <Sparkles className="h-3.5 w-3.5" />Auto-completed
          </span>
        ) : null}
      </div>
      <Button variant="outline" size="sm" className="w-full" onClick={() => onOpenTask(task)} disabled={readOnly}>
        Open
      </Button>
    </div>
  )
}

export function ChecklistBoard({ tasks, loading, readOnly, onOpenTask }: ChecklistBoardProps) {
  const inProgress = tasks.filter((task) => task.status === "in_progress")
  const notStarted = tasks
    .filter((task) => task.status === "not_started" || task.status === "blocked")
    .sort((a, b) => a.order_index - b.order_index)
  const completed = tasks.filter((task) => task.status === "completed" || task.status === "skipped")

  const sections: Array<{ key: string; title: string; rows: ChecklistTaskItem[] }> = [
    { key: "in-progress", title: "IN PROGRESS", rows: inProgress },
    { key: "not-started", title: "NOT STARTED", rows: notStarted },
    { key: "completed", title: "COMPLETED", rows: completed },
  ]

  if (loading) {
    return <div className="h-48 animate-pulse rounded-lg bg-muted" />
  }

  return (
    <div className="space-y-6">
      {sections.map((section) => (
        <section key={section.key}>
          <h3 className="mb-3 text-xs font-semibold tracking-[0.2em] text-muted-foreground">{section.title}</h3>
          {section.rows.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No tasks in this section.</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {section.rows.map((task) => (
                <TaskCard key={task.id} task={task} readOnly={readOnly} onOpenTask={onOpenTask} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
