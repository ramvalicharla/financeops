"use client"

import { useCallback, useMemo, useState } from "react"
import {
  createReportDefinition,
  deleteReportDefinition,
  fetchMetrics,
  fetchReportDefinitions,
  fetchReportRuns,
  runReport,
  updateReportDefinition,
} from "@/lib/api/report-builder"
import {
  type CreateReportDefinitionRequest,
  type MetricDefinition,
  type ReportDefinitionResponse,
  ReportExportFormat,
  type ReportRunResponse,
  ReportRunStatus,
  SortDirection,
} from "@/lib/types/report-builder"
import { useAsyncAction, useFetch, usePolling } from "@/hooks"

export type ActiveReportTab = "runs" | "definitions"
export type ReportSheetMode = "create" | "edit"
type ConfirmState = {
  open: boolean
  title: string
  description: string
  variant: "default" | "destructive"
  onConfirm: () => void
}

export interface ReportFormState {
  name: string
  description: string
  exportFormats: ReportExportFormat[]
  metricKeys: string[]
  periodStart: string
  periodEnd: string
  entityIds: string[]
  entityInput: string
  amountMin: string
  amountMax: string
  tags: string[]
  tagsInput: string
  groupBy: string[]
  sortField: string
  sortDirection: SortDirection
  configText: string
}

const activeRunStatuses = [ReportRunStatus.PENDING, ReportRunStatus.RUNNING]

export const exportFormatOptions = [
  ReportExportFormat.CSV,
  ReportExportFormat.EXCEL,
  ReportExportFormat.PDF,
] as const

const decimalPattern = /^-?\d+(\.\d+)?$/
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const parseCommaSeparated = (raw: string): string[] =>
  raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)

export const formatDateTime = (value: string | null): string => {
  if (!value) return "-"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

const createInitialFormState = (): ReportFormState => ({
  name: "",
  description: "",
  exportFormats: [...exportFormatOptions],
  metricKeys: [],
  periodStart: "",
  periodEnd: "",
  entityIds: [],
  entityInput: "",
  amountMin: "",
  amountMax: "",
  tags: [],
  tagsInput: "",
  groupBy: [],
  sortField: "",
  sortDirection: SortDirection.ASC,
  configText: "{}",
})

const formStateFromDefinition = (
  definition: ReportDefinitionResponse,
): ReportFormState => {
  const sortConfig =
    definition.sort_config &&
    typeof definition.sort_config === "object" &&
    "field" in definition.sort_config &&
    typeof definition.sort_config.field === "string"
      ? definition.sort_config
      : null

  return {
    name: definition.name,
    description: definition.description ?? "",
    exportFormats: definition.export_formats.filter((format) =>
      exportFormatOptions.includes(format as ReportExportFormat),
    ) as ReportExportFormat[],
    metricKeys: [...definition.metric_keys],
    periodStart: definition.filter_config.period_start ?? "",
    periodEnd: definition.filter_config.period_end ?? "",
    entityIds: [...definition.filter_config.entity_ids],
    entityInput: "",
    amountMin: definition.filter_config.amount_min ?? "",
    amountMax: definition.filter_config.amount_max ?? "",
    tags: [...definition.filter_config.tags],
    tagsInput: "",
    groupBy: [...definition.group_by],
    sortField: sortConfig?.field ?? "",
    sortDirection:
      sortConfig?.direction === SortDirection.DESC
        ? SortDirection.DESC
        : SortDirection.ASC,
    configText: JSON.stringify(definition.config ?? {}, null, 2),
  }
}

export function useReports() {
  const [activeTab, setActiveTab] = useState<ActiveReportTab>("runs")
  const [metrics, setMetrics] = useState<MetricDefinition[]>([])
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [definitionActionError, setDefinitionActionError] = useState<string | null>(
    null,
  )
  const [runActionError, setRunActionError] = useState<string | null>(null)
  const [sheetError, setSheetError] = useState<string | null>(null)
  const [sheetMode, setSheetMode] = useState<ReportSheetMode | null>(null)
  const [editingDefinitionId, setEditingDefinitionId] = useState<string | null>(
    null,
  )
  const [step, setStep] = useState(1)
  const [savingDefinition, setSavingDefinition] = useState(false)
  const [runningDefinitionId, setRunningDefinitionId] = useState<string | null>(
    null,
  )
  const [formState, setFormState] = useState<ReportFormState>(
    createInitialFormState(),
  )
  const [runDialogDefinition, setRunDialogDefinition] =
    useState<ReportDefinitionResponse | null>(null)
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null)

  const definitionsQuery = useFetch(() => fetchReportDefinitions(false), [])
  const runsQuery = useFetch(() => fetchReportRuns({ limit: 50 }), [])

  const definitions = definitionsQuery.data ?? []
  const runs = runsQuery.data ?? []
  const loadingDefinitions = definitionsQuery.isLoading
  const loadingRuns = runsQuery.isLoading
  const definitionError =
    definitionActionError ?? definitionsQuery.error?.message ?? null
  const runError = runActionError ?? runsQuery.error?.message ?? null

  const definitionNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const definition of definitions) map.set(definition.id, definition.name)
    return map
  }, [definitions])

  const metricByKey = useMemo(() => {
    const map = new Map<string, MetricDefinition>()
    for (const metric of metrics) map.set(metric.key, metric)
    return map
  }, [metrics])

  const groupedMetrics = useMemo(() => {
    const grouped = new Map<string, MetricDefinition[]>()
    for (const metric of metrics) {
      const list = grouped.get(metric.engine) ?? []
      list.push(metric)
      grouped.set(metric.engine, list)
    }
    return Array.from(grouped.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [metrics])

  const loadDefinitions = useCallback(async () => {
    setDefinitionActionError(null)
    await definitionsQuery.refetch()
  }, [definitionsQuery])

  const loadRuns = useCallback(async () => {
    setRunActionError(null)
    await runsQuery.refetch()
  }, [runsQuery])

  const loadMetrics = useCallback(async () => {
    setLoadingMetrics(true)
    try {
      setMetrics(await fetchMetrics())
    } catch {
      setMetrics([])
    } finally {
      setLoadingMetrics(false)
    }
  }, [])

  const hasActiveRuns = runs.some((run) => activeRunStatuses.includes(run.status))

  usePolling(
    async () => {
      await loadRuns()
    },
    5000,
    activeTab === "runs" && hasActiveRuns,
  )

  const saveDefinitionAction = useAsyncAction(async (body: CreateReportDefinitionRequest) => {
    if (sheetMode === "edit" && editingDefinitionId) {
      await updateReportDefinition(editingDefinitionId, body)
    } else {
      await createReportDefinition(body)
    }
    await loadDefinitions()
  })

  const deleteDefinitionActionState = useAsyncAction(async (id: string) => {
    await deleteReportDefinition(id)
    await loadDefinitions()
  })

  const runDefinitionActionState = useAsyncAction(async (id: string) => {
    await runReport(id)
    setActiveTab("runs")
    closeRunDialog()
    await loadRuns()
  })

  const setForm = (updates: Partial<ReportFormState>) =>
    setFormState((previous) => ({ ...previous, ...updates }))

  const closeSheet = () => {
    setSheetMode(null)
    setEditingDefinitionId(null)
    setStep(1)
    setSheetError(null)
    setFormState(createInitialFormState())
  }

  const openCreateSheet = async () => {
    setSheetMode("create")
    setEditingDefinitionId(null)
    setStep(1)
    setSheetError(null)
    setFormState(createInitialFormState())
    if (!metrics.length) await loadMetrics()
  }

  const openEditSheet = async (definition: ReportDefinitionResponse) => {
    setSheetMode("edit")
    setEditingDefinitionId(definition.id)
    setStep(1)
    setSheetError(null)
    setFormState(formStateFromDefinition(definition))
    if (!metrics.length) await loadMetrics()
  }

  const validateStep = (targetStep: number): boolean => {
    if (targetStep === 1) {
      if (!formState.name.trim()) return setSheetError("Name is required."), false
      if (!formState.exportFormats.length) {
        return setSheetError("Select at least one export format."), false
      }
    }
    if (targetStep === 2 && !formState.metricKeys.length) {
      return setSheetError("Select at least one metric."), false
    }
    if (targetStep === 3) {
      if (
        formState.periodStart &&
        formState.periodEnd &&
        formState.periodEnd < formState.periodStart
      ) {
        return (
          setSheetError("Period End must be on or after Period Start."),
          false
        )
      }
      if (
        formState.amountMin &&
        !decimalPattern.test(formState.amountMin.trim())
      ) {
        return setSheetError("Amount Min must be a decimal string."), false
      }
      if (
        formState.amountMax &&
        !decimalPattern.test(formState.amountMax.trim())
      ) {
        return setSheetError("Amount Max must be a decimal string."), false
      }
    }
    if (
      targetStep === 4 &&
      formState.sortField &&
      !formState.metricKeys.includes(formState.sortField)
    ) {
      return setSheetError("Sort field must be one of selected metrics."), false
    }
    setSheetError(null)
    return true
  }

  const saveDefinition = async () => {
    if (![1, 2, 3, 4].every((targetStep) => validateStep(targetStep))) return

    let parsedConfig: Record<string, unknown>
    try {
      const parsed = JSON.parse(formState.configText || "{}")
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return setSheetError("Config must be a JSON object.")
      }
      parsedConfig = parsed as Record<string, unknown>
    } catch {
      return setSheetError("Config JSON is invalid.")
    }

    const body: CreateReportDefinitionRequest = {
      name: formState.name.trim(),
      description: formState.description.trim() || null,
      metric_keys: formState.metricKeys,
      filter_config: {
        conditions: [],
        period_start: formState.periodStart || null,
        period_end: formState.periodEnd || null,
        entity_ids: formState.entityIds,
        account_codes: [],
        tags: formState.tags,
        amount_min: formState.amountMin.trim() || null,
        amount_max: formState.amountMax.trim() || null,
      },
      group_by: formState.groupBy,
      sort_config: formState.sortField
        ? { field: formState.sortField, direction: formState.sortDirection }
        : undefined,
      export_formats: [...formState.exportFormats],
      config: parsedConfig,
    }

    try {
      await saveDefinitionAction.execute(body)
      setActiveTab("definitions")
      closeSheet()
    } catch (error) {
      setSheetError(error instanceof Error ? error.message : "Save failed.")
    }
  }

  const deleteDefinitionAction = async (id: string) => {
    setConfirmState({
      open: true,
      title: "Delete report",
      description:
        "This will permanently delete the report definition and all associated run history. This cannot be undone.",
      variant: "destructive",
      onConfirm: () => {
        void executeDeleteDefinition(id)
      },
    })
  }

  const openRunDialog = (definition: ReportDefinitionResponse) => {
    setRunDialogDefinition(definition)
  }

  const closeRunDialog = () => {
    setRunDialogDefinition(null)
  }

  const dismissConfirm = useCallback(() => {
    setConfirmState(null)
  }, [])

  const executeDeleteDefinition = useCallback(
    async (id: string) => {
      try {
        setDefinitionActionError(null)
        await deleteDefinitionActionState.execute(id)
      } catch (error) {
        setDefinitionActionError(
          error instanceof Error ? error.message : "Delete failed.",
        )
      } finally {
        dismissConfirm()
      }
    },
    [deleteDefinitionActionState, dismissConfirm],
  )

  const runDefinitionAction = async (id: string) => {
    setRunningDefinitionId(id)
    try {
      setRunActionError(null)
      await runDefinitionActionState.execute(id)
    } catch (error) {
      setRunActionError(error instanceof Error ? error.message : "Run failed.")
    } finally {
      setRunningDefinitionId(null)
    }
  }

  const addEntityIds = () => {
    const values = parseCommaSeparated(formState.entityInput)
    if (!values.length) return

    const invalid = values.find((value) => !uuidPattern.test(value))
    if (invalid) {
      setSheetError(`Invalid entity UUID: ${invalid}`)
      return
    }

    setForm({
      entityIds: Array.from(new Set([...formState.entityIds, ...values])),
      entityInput: "",
    })
    setSheetError(null)
  }

  const addTags = () => {
    setForm({
      tags: Array.from(
        new Set([...formState.tags, ...parseCommaSeparated(formState.tagsInput)]),
      ),
      tagsInput: "",
    })
  }

  return {
    activeTab,
    addEntityIds,
    addTags,
    closeRunDialog,
    closeSheet,
    confirmLoading: deleteDefinitionActionState.isLoading,
    confirmState,
    definitionError,
    definitionNameById,
    definitions,
    deleteDefinitionAction,
    dismissConfirm,
    formState,
    groupedMetrics,
    loadRuns,
    loadingDefinitions,
    loadingMetrics,
    loadingRuns,
    metricByKey,
    openCreateSheet,
    openEditSheet,
    openRunDialog,
    runDefinitionAction,
    runDialogDefinition,
    runError,
    runningDefinitionId,
    runs,
    saveDefinition,
    savingDefinition: saveDefinitionAction.isLoading,
    setActiveTab,
    setForm,
    setStep,
    sheetError,
    sheetMode,
    step,
    validateStep,
  }
}
