"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { CalendarClock, Loader2, Play, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { fetchDefinitions } from "@/lib/api/board-pack"
import { fetchReportDefinitions } from "@/lib/api/report-builder"
import {
  createDeliverySchedule,
  deleteDeliverySchedule,
  fetchDeliverySchedules,
  triggerDeliverySchedule,
  updateDeliverySchedule,
} from "@/lib/api/scheduled-delivery"
import {
  DeliveryExportFormat,
  type DeliveryRecipient,
  type DeliveryScheduleResponse,
  RecipientType,
  ScheduleType,
} from "@/lib/types/scheduled-delivery"
import { cn } from "@/lib/utils"

interface SourceOption {
  id: string
  name: string
}

interface ScheduleFormState {
  name: string
  description: string
  scheduleType: ScheduleType
  sourceDefinitionId: string
  cronExpression: string
  timezone: string
  exportFormat: DeliveryExportFormat
  recipients: DeliveryRecipient[]
}

const createDefaultForm = (): ScheduleFormState => ({
  name: "",
  description: "",
  scheduleType: ScheduleType.BOARD_PACK,
  sourceDefinitionId: "",
  cronExpression: "0 8 * * 1",
  timezone: "UTC",
  exportFormat: DeliveryExportFormat.PDF,
  recipients: [{ type: RecipientType.EMAIL, address: "" }],
})

const statusBadge = (isActive: boolean): string =>
  isActive
    ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
    : "bg-muted text-muted-foreground"

const formatDateTime = (value: string | null): string => {
  if (!value) return "-"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

const validateForm = (state: ScheduleFormState): string | null => {
  if (!state.name.trim()) return "Name is required."
  if (!state.sourceDefinitionId) return "Source definition is required."
  if (state.cronExpression.trim().split(/\s+/).length !== 5) {
    return "Cron Expression must have 5 fields."
  }
  if (!state.recipients.length) return "At least one recipient is required."
  for (const recipient of state.recipients) {
    const address = recipient.address.trim()
    if (!address) return "Recipient address is required."
    if (recipient.type === RecipientType.EMAIL && !address.includes("@")) {
      return "Email recipient must contain @."
    }
    if (
      recipient.type === RecipientType.WEBHOOK &&
      !(address.startsWith("http://") || address.startsWith("https://"))
    ) {
      return "Webhook recipient must start with http:// or https://."
    }
  }
  return null
}

interface ScheduleSheetProps {
  title: string
  open: boolean
  submitting: boolean
  loadingSources: boolean
  error: string | null
  formState: ScheduleFormState
  sourceOptions: SourceOption[]
  onClose: () => void
  onSubmit: () => void
  onChange: (updates: Partial<ScheduleFormState>) => void
  onRecipientChange: (index: number, updates: Partial<DeliveryRecipient>) => void
  onAddRecipient: () => void
  onRemoveRecipient: (index: number) => void
}

function ScheduleSheet({
  title,
  open,
  submitting,
  loadingSources,
  error,
  formState,
  sourceOptions,
  onClose,
  onSubmit,
  onChange,
  onRecipientChange,
  onAddRecipient,
  onRemoveRecipient,
}: ScheduleSheetProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60">
      <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Close
          </Button>
        </div>

        <div className="mt-4 space-y-4">
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
        </div>

        <div className="mt-5 flex justify-end gap-2">
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
      </aside>
    </div>
  )
}

function CreateScheduleSheet(props: Omit<ScheduleSheetProps, "title">) {
  return <ScheduleSheet {...props} title="Create Schedule" />
}

function EditScheduleSheet(props: Omit<ScheduleSheetProps, "title">) {
  return <ScheduleSheet {...props} title="Edit Schedule" />
}

export default function ScheduledDeliveryPage() {
  const [schedules, setSchedules] = useState<DeliveryScheduleResponse[]>([])
  const [sourceOptions, setSourceOptions] = useState<SourceOption[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingSources, setLoadingSources] = useState(false)
  const [saving, setSaving] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sheetError, setSheetError] = useState<string | null>(null)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [sheetMode, setSheetMode] = useState<"create" | "edit" | null>(null)
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null)
  const [formState, setFormState] = useState<ScheduleFormState>(createDefaultForm())

  const definitionNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const option of sourceOptions) {
      map.set(option.id, option.name)
    }
    for (const schedule of schedules) {
      if (!map.has(schedule.source_definition_id)) {
        map.set(schedule.source_definition_id, schedule.source_definition_id)
      }
    }
    return map
  }, [sourceOptions, schedules])

  const loadSchedules = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setSchedules(await fetchDeliverySchedules())
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load schedules.")
      setSchedules([])
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSources = useCallback(async (scheduleType: ScheduleType) => {
    setLoadingSources(true)
    try {
      if (scheduleType === ScheduleType.BOARD_PACK) {
        const definitions = await fetchDefinitions(true)
        setSourceOptions(
          definitions.map((item) => ({
            id: item.id,
            name: item.name,
          })),
        )
      } else {
        const definitions = await fetchReportDefinitions(true)
        setSourceOptions(
          definitions.map((item) => ({
            id: item.id,
            name: item.name,
          })),
        )
      }
    } catch {
      setSourceOptions([])
    } finally {
      setLoadingSources(false)
    }
  }, [])

  useEffect(() => {
    void loadSchedules()
  }, [loadSchedules])

  useEffect(() => {
    if (!sheetMode) return
    void loadSources(formState.scheduleType)
  }, [formState.scheduleType, loadSources, sheetMode])

  useEffect(() => {
    if (!toastMessage) return
    const timeoutId = window.setTimeout(() => setToastMessage(null), 3000)
    return () => window.clearTimeout(timeoutId)
  }, [toastMessage])

  const closeSheet = () => {
    setSheetMode(null)
    setEditingScheduleId(null)
    setFormState(createDefaultForm())
    setSheetError(null)
  }

  const openCreateSheet = () => {
    setSheetMode("create")
    setEditingScheduleId(null)
    setFormState(createDefaultForm())
    setSheetError(null)
  }

  const openEditSheet = (schedule: DeliveryScheduleResponse) => {
    setSheetMode("edit")
    setEditingScheduleId(schedule.id)
    setFormState({
      name: schedule.name,
      description: schedule.description ?? "",
      scheduleType: schedule.schedule_type,
      sourceDefinitionId: schedule.source_definition_id,
      cronExpression: schedule.cron_expression,
      timezone: schedule.timezone,
      exportFormat: schedule.export_format,
      recipients:
        schedule.recipients.length > 0
          ? schedule.recipients
          : [{ type: RecipientType.EMAIL, address: "" }],
    })
    setSheetError(null)
  }

  const setForm = (updates: Partial<ScheduleFormState>) => {
    setFormState((previous) => ({ ...previous, ...updates }))
  }

  const setRecipient = (index: number, updates: Partial<DeliveryRecipient>) => {
    setFormState((previous) => {
      const next = [...previous.recipients]
      next[index] = { ...next[index], ...updates }
      return { ...previous, recipients: next }
    })
  }

  const addRecipient = () => {
    setFormState((previous) => ({
      ...previous,
      recipients: [...previous.recipients, { type: RecipientType.EMAIL, address: "" }],
    }))
  }

  const removeRecipient = (index: number) => {
    setFormState((previous) => ({
      ...previous,
      recipients: previous.recipients.filter((_, idx) => idx !== index),
    }))
  }

  const saveSchedule = async () => {
    const validationError = validateForm(formState)
    if (validationError) {
      setSheetError(validationError)
      return
    }

    setSaving(true)
    setSheetError(null)
    try {
      const payload = {
        name: formState.name.trim(),
        description: formState.description.trim() || null,
        schedule_type: formState.scheduleType,
        source_definition_id: formState.sourceDefinitionId,
        cron_expression: formState.cronExpression.trim(),
        timezone: formState.timezone.trim() || "UTC",
        recipients: formState.recipients.map((recipient) => ({
          type: recipient.type,
          address: recipient.address.trim(),
        })),
        export_format: formState.exportFormat,
        config: {},
      }
      if (sheetMode === "edit" && editingScheduleId) {
        await updateDeliverySchedule(editingScheduleId, payload)
      } else {
        await createDeliverySchedule(payload)
      }
      await loadSchedules()
      closeSheet()
    } catch (cause) {
      setSheetError(cause instanceof Error ? cause.message : "Failed to save schedule.")
    } finally {
      setSaving(false)
    }
  }

  const triggerNow = async (scheduleId: string) => {
    setRunningId(scheduleId)
    try {
      await triggerDeliverySchedule(scheduleId)
      setToastMessage("Schedule triggered successfully.")
      await loadSchedules()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trigger failed.")
    } finally {
      setRunningId(null)
    }
  }

  const deleteScheduleAction = async (scheduleId: string) => {
    if (!window.confirm("Delete this schedule? This performs a soft delete.")) return
    try {
      await deleteDeliverySchedule(scheduleId)
      await loadSchedules()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Delete failed.")
    }
  }

  const isCreateOpen = sheetMode === "create"
  const isEditOpen = sheetMode === "edit"

  return (
    <div className="space-y-6">
      {toastMessage ? (
        <div className="fixed right-4 top-4 z-[60] rounded-md border border-[hsl(var(--brand-success)/0.5)] bg-[hsl(var(--brand-success)/0.2)] px-3 py-2 text-sm text-[hsl(var(--brand-success))]">
          {toastMessage}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Scheduled Delivery</h1>
          <p className="text-sm text-muted-foreground">
            Configure recurring board pack/report deliveries to email or webhook recipients.
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" asChild>
            <Link href="/scheduled-delivery/logs">View Logs</Link>
          </Button>
          <Button type="button" onClick={openCreateSheet}>
            <CalendarClock className="mr-2 h-4 w-4" />
            New Schedule
          </Button>
        </div>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <section className="rounded-lg border border-border bg-card p-4">
        {loading ? (
          <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
        ) : null}
        {!loading && !schedules.length ? (
          <p className="rounded-md border border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
            No delivery schedules yet.
          </p>
        ) : null}
        {!!schedules.length ? (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[1020px] text-sm">
              <thead>
                <tr className="bg-muted/30">
                  <th className="px-3 py-2 text-left font-medium text-foreground">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Type</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Source</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Cron</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Next Run</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Active</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((schedule) => (
                  <tr key={schedule.id} className="border-t border-border">
                    <td className="px-3 py-2 text-muted-foreground">{schedule.name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{schedule.schedule_type}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {definitionNameById.get(schedule.source_definition_id) ??
                        schedule.source_definition_id}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {schedule.cron_expression}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {formatDateTime(schedule.next_run_at)}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                          statusBadge(schedule.is_active),
                        )}
                      >
                        {schedule.is_active ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={!schedule.is_active || runningId === schedule.id}
                          onClick={() => {
                            void triggerNow(schedule.id)
                          }}
                        >
                          {runningId === schedule.id ? (
                            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="mr-1 h-3.5 w-3.5" />
                          )}
                          Trigger Now
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => openEditSheet(schedule)}
                        >
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            void deleteScheduleAction(schedule.id)
                          }}
                        >
                          <Trash2 className="mr-1 h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <CreateScheduleSheet
        open={isCreateOpen}
        submitting={saving}
        loadingSources={loadingSources}
        error={sheetError}
        formState={formState}
        sourceOptions={sourceOptions}
        onClose={closeSheet}
        onSubmit={() => {
          void saveSchedule()
        }}
        onChange={setForm}
        onRecipientChange={setRecipient}
        onAddRecipient={addRecipient}
        onRemoveRecipient={removeRecipient}
      />

      <EditScheduleSheet
        open={isEditOpen}
        submitting={saving}
        loadingSources={loadingSources}
        error={sheetError}
        formState={formState}
        sourceOptions={sourceOptions}
        onClose={closeSheet}
        onSubmit={() => {
          void saveSchedule()
        }}
        onChange={setForm}
        onRecipientChange={setRecipient}
        onAddRecipient={addRecipient}
        onRemoveRecipient={removeRecipient}
      />
    </div>
  )
}
