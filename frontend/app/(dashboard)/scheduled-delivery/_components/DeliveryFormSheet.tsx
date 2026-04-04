"use client"

import { Loader2 } from "lucide-react"
import { Sheet } from "@/components/ui/Sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  DeliveryExportFormat,
  type DeliveryRecipient,
  RecipientType,
  ScheduleType,
} from "@/lib/types/scheduled-delivery"
import type {
  ScheduleFormState,
  SourceOption,
} from "../_hooks/useDeliveries"

interface DeliveryFormSheetProps {
  error: string | null
  formState: ScheduleFormState
  loadingSources: boolean
  open: boolean
  sourceOptions: SourceOption[]
  submitting: boolean
  title: string
  onAddRecipient: () => void
  onChange: (updates: Partial<ScheduleFormState>) => void
  onClose: () => void
  onRecipientChange: (index: number, updates: Partial<DeliveryRecipient>) => void
  onRemoveRecipient: (index: number) => void
  onSubmit: () => void
}

export function DeliveryFormSheet({
  error,
  formState,
  loadingSources,
  open,
  sourceOptions,
  submitting,
  title,
  onAddRecipient,
  onChange,
  onClose,
  onRecipientChange,
  onRemoveRecipient,
  onSubmit,
}: DeliveryFormSheetProps) {
  return (
    <Sheet
      open={open}
      onClose={submitting ? () => undefined : onClose}
      title={title}
      width="max-w-xl"
    >
      <div className="space-y-4">
        <div className="space-y-1">
          <label className="text-sm text-foreground" htmlFor="delivery-name">
            Name
          </label>
          <Input
            id="delivery-name"
            value={formState.name}
            onChange={(event) => onChange({ name: event.target.value })}
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm text-foreground" htmlFor="delivery-description">
            Description
          </label>
          <textarea
            id="delivery-description"
            className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={formState.description}
            onChange={(event) => onChange({ description: event.target.value })}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="delivery-type">
              Type
            </label>
            <select
              id="delivery-type"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={formState.scheduleType}
              onChange={(event) =>
                onChange({
                  scheduleType:
                    event.target.value === ScheduleType.REPORT
                      ? ScheduleType.REPORT
                      : ScheduleType.BOARD_PACK,
                  sourceDefinitionId: "",
                })
              }
            >
              <option value={ScheduleType.BOARD_PACK}>Board Pack</option>
              <option value={ScheduleType.REPORT}>Report</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="delivery-source">
              Source Definition
            </label>
            <select
              id="delivery-source"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={formState.sourceDefinitionId}
              onChange={(event) => onChange({ sourceDefinitionId: event.target.value })}
            >
              <option value="">Select source</option>
              {sourceOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
            {loadingSources ? (
              <p className="text-xs text-muted-foreground">Loading definitions...</p>
            ) : null}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-sm text-foreground" htmlFor="delivery-cron">
            Cron Expression
          </label>
          <Input
            id="delivery-cron"
            value={formState.cronExpression}
            onChange={(event) => onChange({ cronExpression: event.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            Format: minute hour day month weekday
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="delivery-timezone">
              Timezone
            </label>
            <Input
              id="delivery-timezone"
              value={formState.timezone}
              onChange={(event) => onChange({ timezone: event.target.value })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="delivery-export">
              Export Format
            </label>
            <select
              id="delivery-export"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={formState.exportFormat}
              onChange={(event) =>
                onChange({
                  exportFormat:
                    event.target.value === DeliveryExportFormat.EXCEL
                      ? DeliveryExportFormat.EXCEL
                      : event.target.value === DeliveryExportFormat.CSV
                        ? DeliveryExportFormat.CSV
                        : DeliveryExportFormat.PDF,
                })
              }
            >
              <option value={DeliveryExportFormat.PDF}>PDF</option>
              <option value={DeliveryExportFormat.EXCEL}>Excel</option>
              <option value={DeliveryExportFormat.CSV}>CSV</option>
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm text-foreground">Recipients</p>
            <Button type="button" variant="outline" size="sm" onClick={onAddRecipient}>
              Add Recipient
            </Button>
          </div>
          <div className="space-y-2">
            {formState.recipients.map((recipient, index) => (
              <div key={index} className="grid gap-2 sm:grid-cols-[160px_1fr_auto]">
                <select
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={recipient.type}
                  onChange={(event) =>
                    onRecipientChange(index, {
                      type:
                        event.target.value === RecipientType.WEBHOOK
                          ? RecipientType.WEBHOOK
                          : RecipientType.EMAIL,
                    })
                  }
                >
                  <option value={RecipientType.EMAIL}>Email</option>
                  <option value={RecipientType.WEBHOOK}>Webhook</option>
                </select>
                <Input
                  value={recipient.address}
                  onChange={(event) =>
                    onRecipientChange(index, { address: event.target.value })
                  }
                  placeholder={
                    recipient.type === RecipientType.EMAIL
                      ? "name@example.com"
                      : "https://hooks.example.com/endpoint"
                  }
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onRemoveRecipient(index)}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
        </div>

        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="button" onClick={onSubmit} disabled={submitting}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save"
            )}
          </Button>
        </div>
      </div>
    </Sheet>
  )
}
