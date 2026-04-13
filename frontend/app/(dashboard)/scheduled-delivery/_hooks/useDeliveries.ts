"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
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
import { useAsyncAction, useFetch } from "@/hooks"

export interface SourceOption {
  id: string
  name: string
}
type ConfirmState = {
  open: boolean
  title: string
  description: string
  variant: "default" | "destructive"
  onConfirm: () => void
}

export interface ScheduleFormState {
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

export const formatDateTime = (value: string | null): string => {
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

export function useDeliveries() {
  const [sourceOptions, setSourceOptions] = useState<SourceOption[]>([])
  const [loadingSources, setLoadingSources] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [sheetError, setSheetError] = useState<string | null>(null)
  const [sheetMode, setSheetMode] = useState<"create" | "edit" | null>(null)
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null)
  const [formState, setFormState] = useState<ScheduleFormState>(createDefaultForm())
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null)

  const schedulesQuery = useFetch(() => fetchDeliverySchedules(), [])
  const schedules = schedulesQuery.data ?? []
  const loading = schedulesQuery.isLoading
  const error = actionError ?? schedulesQuery.error?.message ?? null

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
    setActionError(null)
    await schedulesQuery.refetch()
  }, [schedulesQuery])

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
    if (!sheetMode) return
    void loadSources(formState.scheduleType)
  }, [formState.scheduleType, loadSources, sheetMode])

  const saveScheduleAction = useAsyncAction(
    async (payload: {
      name: string
      description: string | null
      schedule_type: ScheduleType
      source_definition_id: string
      cron_expression: string
      timezone: string
      recipients: DeliveryRecipient[]
      export_format: DeliveryExportFormat
      config: Record<string, unknown>
    }) => {
      if (sheetMode === "edit" && editingScheduleId) {
        await updateDeliverySchedule(editingScheduleId, payload)
      } else {
        await createDeliverySchedule(payload)
      }
      await loadSchedules()
      closeSheet()
    },
  )

  const triggerNowAction = useAsyncAction(async (scheduleId: string) => {
    await triggerDeliverySchedule(scheduleId)
    toast.success("Schedule triggered successfully.")
    await loadSchedules()
  })

  const deleteScheduleActionState = useAsyncAction(async (scheduleId: string) => {
    await deleteDeliverySchedule(scheduleId)
    await loadSchedules()
  })

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

  const dismissConfirm = useCallback(() => {
    setConfirmState(null)
  }, [])

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
        config: {} as Record<string, unknown>,
      }
      await saveScheduleAction.execute(payload)
    } catch (cause) {
      setSheetError(cause instanceof Error ? cause.message : "Failed to save schedule.")
    }
  }

  const triggerNow = async (scheduleId: string) => {
    setRunningId(scheduleId)
    try {
      setActionError(null)
      await triggerNowAction.execute(scheduleId)
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Trigger failed.")
    } finally {
      setRunningId(null)
    }
  }

  const deleteScheduleAction = async (scheduleId: string) => {
    setConfirmState({
      open: true,
      title: "Delete delivery schedule",
      description:
        "This will permanently delete this delivery schedule. Scheduled deliveries will no longer be sent. This cannot be undone.",
      variant: "destructive",
      onConfirm: () => {
        void (async () => {
          try {
            setActionError(null)
            await deleteScheduleActionState.execute(scheduleId)
          } catch (cause) {
            setActionError(cause instanceof Error ? cause.message : "Delete failed.")
          } finally {
            dismissConfirm()
          }
        })()
      },
    })
  }

  return {
    addRecipient,
    closeSheet,
    confirmLoading: deleteScheduleActionState.isLoading,
    confirmState,
    definitionNameById,
    deleteScheduleAction,
    dismissConfirm,
    error,
    formState,
    loading,
    loadingSources,
    openCreateSheet,
    openEditSheet,
    removeRecipient,
    runningId,
    saveSchedule,
    saving: saveScheduleAction.isLoading,
    schedules,
    setForm,
    setRecipient,
    sheetError,
    sheetMode,
    sourceOptions,
    triggerNow,
  }
}
