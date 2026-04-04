"use client"

import { Loader2 } from "lucide-react"
import { Dialog } from "@/components/ui/Dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { DefinitionResponse } from "@/lib/types/board-pack"

interface BoardPackRunDialogProps {
  activeDefinitions: DefinitionResponse[]
  definitionId: string
  error: string | null
  open: boolean
  periodEnd: string
  periodStart: string
  submitting: boolean
  onClose: () => void
  onDefinitionChange: (definitionId: string) => void
  onGenerate: () => void
  onPeriodEndChange: (value: string) => void
  onPeriodStartChange: (value: string) => void
}

export function BoardPackRunDialog({
  activeDefinitions,
  definitionId,
  error,
  open,
  periodEnd,
  periodStart,
  submitting,
  onClose,
  onDefinitionChange,
  onGenerate,
  onPeriodEndChange,
  onPeriodStartChange,
}: BoardPackRunDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={submitting ? () => undefined : onClose}
      title="Generate Board Pack"
      size="md"
    >
      <div className="space-y-4">
        <div className="space-y-1">
          <label className="text-sm text-foreground" htmlFor="generate-definition">
            Definition
          </label>
          <select
            id="generate-definition"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={definitionId}
            onChange={(event) => onDefinitionChange(event.target.value)}
          >
            <option value="">Select definition</option>
            {activeDefinitions.map((definition) => (
              <option key={definition.id} value={definition.id}>
                {definition.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="generate-period-start">
              Period Start
            </label>
            <Input
              id="generate-period-start"
              type="date"
              value={periodStart}
              onChange={(event) => onPeriodStartChange(event.target.value)}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="generate-period-end">
              Period End
            </label>
            <Input
              id="generate-period-end"
              type="date"
              value={periodEnd}
              onChange={(event) => onPeriodEndChange(event.target.value)}
            />
          </div>
        </div>

        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button type="button" onClick={onGenerate} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              "Generate"
            )}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
