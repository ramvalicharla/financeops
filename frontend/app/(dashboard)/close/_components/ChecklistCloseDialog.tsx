"use client"

import { useEffect, useState } from "react"
import { Dialog } from "@/components/ui/Dialog"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"

interface ChecklistCloseDialogProps {
  open: boolean
  checklistLabel: string
  onConfirm: (notes: string) => void
  onCancel: () => void
}

export function ChecklistCloseDialog({
  open,
  checklistLabel,
  onConfirm,
  onCancel,
}: ChecklistCloseDialogProps) {
  const [notes, setNotes] = useState("")

  useEffect(() => {
    if (!open) {
      setNotes("")
    }
  }, [open])

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={`Close ${checklistLabel}`}
      description="This records the checklist close event. Closed-by attribution is not exposed by the current API, so the UI only shows closed_at and the close notes."
      size="sm"
    >
      <div className="space-y-4">
        <FormField
          id="monthend-close-notes"
          label="Close notes"
          hint="Optional context recorded with the close action"
        >
          <textarea
            id="monthend-close-notes"
            className="min-h-28 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </FormField>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" onClick={() => onConfirm(notes.trim())}>
            Close checklist
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
