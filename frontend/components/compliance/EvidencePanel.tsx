"use client"

import { useState } from "react"
import { Sheet } from "@/components/ui/Sheet"
import type { ComplianceControl } from "@/lib/types/compliance"

interface EvidencePanelProps {
  framework: "soc2" | "iso27001"
  control: ComplianceControl | null
  open: boolean
  isAdminView: boolean
  onClose: () => void
  onUpdateStatus?: (controlId: string, status: string, notes: string) => Promise<void>
}

export function EvidencePanel({
  framework,
  control,
  open,
  isAdminView,
  onClose,
  onUpdateStatus,
}: EvidencePanelProps) {
  const [status, setStatus] = useState("pass")
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)

  if (!open || !control) {
    return null
  }

  const submit = async () => {
    if (!onUpdateStatus) {
      return
    }
    setSaving(true)
    try {
      await onUpdateStatus(control.control_id, status, notes)
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Evidence" width="max-w-md">
      <h3 className="text-lg font-semibold text-foreground">{control.control_id}</h3>
      <p className="text-sm text-foreground">{control.control_name}</p>
      <p className="mt-2 text-xs text-muted-foreground">{control.control_description ?? "No description"}</p>
      <div className="mt-4 rounded-lg border border-border p-3 text-sm">
        <p className="text-muted-foreground">Current status: {control.status}</p>
        <p className="text-muted-foreground">Last evaluated: {control.last_evaluated_at ?? "-"}</p>
        <p className="mt-2 text-foreground">Evidence: {control.evidence_summary ?? "No evidence summary"}</p>
      </div>

      <div className="mt-4 rounded-lg border border-border p-3 text-sm">
        <p className="mb-2 font-medium text-foreground">Recent events</p>
        <ul className="space-y-1 text-xs text-muted-foreground">
          <li>{control.last_evaluated_at ? `${control.last_evaluated_at}: status=${control.status}` : "No events yet"}</li>
          <li>Framework: {framework.toUpperCase()}</li>
        </ul>
      </div>

      {isAdminView ? (
        <div className="mt-4 space-y-3 rounded-lg border border-border p-3">
          <p className="text-sm font-medium text-foreground">Manual status update</p>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
          >
            {[
              "not_evaluated",
              "pass",
              "fail",
              "partial",
              "not_applicable",
            ].map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            className="min-h-24 w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
            placeholder="Evidence notes"
          />
          <button
            type="button"
            onClick={() => void submit()}
            disabled={saving}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            {saving ? "Updating..." : "Update Status"}
          </button>
        </div>
      ) : null}
    </Sheet>
  )
}

