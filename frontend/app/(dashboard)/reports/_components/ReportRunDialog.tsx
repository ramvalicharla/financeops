"use client"

import { Loader2, Play } from "lucide-react"
import { Dialog } from "@/components/ui/Dialog"
import { Button } from "@/components/ui/button"
import type { ReportDefinitionResponse } from "@/lib/types/report-builder"

interface ReportRunDialogProps {
  definition: ReportDefinitionResponse | null
  loading: boolean
  onClose: () => void
  onConfirm: (definitionId: string) => void
}

export function ReportRunDialog({
  definition,
  loading,
  onClose,
  onConfirm,
}: ReportRunDialogProps) {
  return (
    <Dialog
      open={Boolean(definition)}
      onClose={loading ? () => undefined : onClose}
      title="Run Report"
      description={
        definition
          ? `Trigger "${definition.name}" now and create a fresh report run.`
          : undefined
      }
      size="sm"
    >
      {definition ? (
        <div className="space-y-4">
          <div className="rounded-md border border-border bg-background px-4 py-3 text-sm text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">Definition:</span>{" "}
              {definition.name}
            </p>
            <p>
              <span className="font-medium text-foreground">Metrics:</span>{" "}
              {definition.metric_keys.length}
            </p>
            <p>
              <span className="font-medium text-foreground">Formats:</span>{" "}
              {definition.export_formats.join(", ")}
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => onConfirm(definition.id)}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Run Now
                </>
              )}
            </Button>
          </div>
        </div>
      ) : null}
    </Dialog>
  )
}
