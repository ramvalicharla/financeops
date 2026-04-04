"use client"

import { Loader2 } from "lucide-react"
import { Dialog } from "./Dialog"
import { Button } from "./button"

export interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "default" | "destructive"
  isLoading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={variant === "destructive" ? `\u26A0 ${title}` : title}
      description={description}
      size="sm"
    >
      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          disabled={isLoading}
          onClick={onCancel}
        >
          {cancelLabel}
        </Button>
        <Button
          type="button"
          variant={variant === "destructive" ? "destructive" : "default"}
          disabled={isLoading}
          onClick={onConfirm}
        >
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  )
}
