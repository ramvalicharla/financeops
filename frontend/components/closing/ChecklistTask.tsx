"use client"

import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Sheet } from "@/components/ui/Sheet"
import type { ChecklistTaskItem } from "@/lib/types/closing"

interface ChecklistTaskProps {
  open: boolean
  task: ChecklistTaskItem | null
  allTasks: ChecklistTaskItem[]
  canAssign: boolean
  readOnly: boolean
  onClose: () => void
  onSave: (taskId: string, status: ChecklistTaskItem["status"], notes: string) => Promise<void>
  onAssign: (taskId: string, userId: string) => Promise<void>
}

const statusOptions: ChecklistTaskItem["status"][] = [
  "not_started",
  "in_progress",
  "completed",
  "blocked",
  "skipped",
]

export function ChecklistTask({
  open,
  task,
  allTasks,
  canAssign,
  readOnly,
  onClose,
  onSave,
  onAssign,
}: ChecklistTaskProps) {
  const [status, setStatus] = useState<ChecklistTaskItem["status"]>("not_started")
  const [notes, setNotes] = useState("")
  const [assignUserId, setAssignUserId] = useState("")
  const [busy, setBusy] = useState(false)

  const dependencyRows = useMemo(() => {
    if (!task) return []
    const ids = new Set(task.depends_on_task_ids)
    return allTasks.filter((item) => ids.has(item.template_task_id))
  }, [allTasks, task])

  useEffect(() => {
    if (!task) return
    setStatus(task.status)
    setNotes(task.notes ?? "")
  }, [task])

  if (!open || !task) {
    return null
  }

  const save = async () => {
    setBusy(true)
    try {
      await onSave(task.id, status, notes)
      onClose()
    } finally {
      setBusy(false)
    }
  }

  const assign = async () => {
    if (!assignUserId.trim()) return
    setBusy(true)
    try {
      await onAssign(task.id, assignUserId.trim())
      setAssignUserId("")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Checklist task" width="max-w-md">
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground">{task.task_name}</h3>
          {task.is_auto_completed ? (
            <p className="text-xs text-emerald-300">
              Auto-completed by {task.auto_completed_by_event ?? "event"}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="checklist-task-status" className="mb-1 block text-sm text-muted-foreground">Status</label>
          <select
            id="checklist-task-status"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={status}
            disabled={readOnly}
            onChange={(event) => setStatus(event.target.value as ChecklistTaskItem["status"])}
          >
            {statusOptions.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm text-muted-foreground">Notes</label>
          <textarea
            className="min-h-[110px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={notes}
            disabled={readOnly}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>

        {canAssign && !readOnly ? (
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Assign User ID</label>
            <div className="flex gap-2">
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={assignUserId}
                onChange={(event) => setAssignUserId(event.target.value)}
                placeholder="UUID"
              />
              <Button onClick={assign} disabled={busy || !assignUserId.trim()} size="sm">Assign</Button>
            </div>
          </div>
        ) : null}

        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">Dependencies</h4>
          {dependencyRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No dependencies.</p>
          ) : (
            <ul className="space-y-1 text-sm text-muted-foreground">
              {dependencyRows.map((row) => (
                <li key={row.id}>
                  Requires: {row.task_name} {row.status === "completed" || row.status === "skipped" ? "✓" : "⏳"}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">History</h4>
          <ul className="space-y-1 text-xs text-muted-foreground">
            <li>Created: {task.due_date ?? "n/a"}</li>
            <li>Completed: {task.completed_at ?? "Not completed"}</li>
          </ul>
        </div>

        <Button className="w-full" onClick={save} disabled={readOnly || busy}>Save Changes</Button>
      </div>
    </Sheet>
  )
}
