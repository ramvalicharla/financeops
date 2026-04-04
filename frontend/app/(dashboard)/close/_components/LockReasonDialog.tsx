"use client"

import { useEffect, useMemo, useState } from "react"
import { Dialog } from "@/components/ui/Dialog"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"

interface LockReasonDialogProps {
  open: boolean
  action: "lock" | "unlock"
  onConfirm: (reason: string) => void
  onCancel: () => void
}

export function LockReasonDialog({
  open,
  action,
  onConfirm,
  onCancel,
}: LockReasonDialogProps) {
  const [reason, setReason] = useState("")

  useEffect(() => {
    if (!open) {
      setReason("")
    }
  }, [open])

  const trimmedReason = reason.trim()
  const isValid = trimmedReason.length >= 10

  const title = action === "lock" ? "Lock Period" : "Unlock Period"
  const description = useMemo(
    () =>
      action === "lock"
        ? "Provide a clear reason for locking this period. This explanation will be recorded in the audit log."
        : "Provide a clear reason for unlocking this period. This explanation will be recorded in the audit log.",
    [action],
  )

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      size="sm"
    >
      <div className="space-y-4">
        <FormField
          id="lock-reason"
          label="Reason"
          required
          hint="This will be recorded in the audit log"
          error={
            reason.length > 0 && !isValid
              ? "Reason must be at least 10 characters."
              : undefined
          }
        >
          <textarea
            id="lock-reason"
            className="min-h-28 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </FormField>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!isValid}
            onClick={() => onConfirm(trimmedReason)}
          >
            Confirm
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
