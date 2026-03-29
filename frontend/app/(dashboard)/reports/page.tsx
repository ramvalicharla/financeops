"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Pencil, Play, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
import { cn } from "@/lib/utils"

type ActiveTab = "runs" | "definitions"
type SheetMode = "create" | "edit"

interface ReportFormState {
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
const exportFormatOptions = [
  ReportExportFormat.CSV,
  ReportExportFormat.EXCEL,
  ReportExportFormat.PDF,
]
const decimalPattern = /^-?\d+(\.\d+)?$/
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

const statusClassMap: Record<ReportRunStatus, string> = {
  [ReportRunStatus.PENDING]: "bg-yellow-500/20 text-yellow-300",
  [ReportRunStatus.RUNNING]: "bg-blue-500/20 text-blue-300",
  [ReportRunStatus.COMPLETE]:
    "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  [ReportRunStatus.FAILED]:
    "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
}

const parseCommaSeparated = (raw: string): string[] =>
  raw
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean)

const formatDateTime = (value: string | null): string => {
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

export default function ReportsPage() {
  const router = useRouter()

  const [activeTab, setActiveTab] = useState<ActiveTab>("runs")
  const [definitions, setDefinitions] = useState<ReportDefinitionResponse[]>([])
  const [runs, setRuns] = useState<ReportRunResponse[]>([])
  const [metrics, setMetrics] = useState<MetricDefinition[]>([])
  const [loadingDefinitions, setLoadingDefinitions] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [definitionError, setDefinitionError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [sheetError, setSheetError] = useState<string | null>(null)
  const [sheetMode, setSheetMode] = useState<SheetMode | null>(null)
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
    setLoadingDefinitions(true)
    setDefinitionError(null)
    try {
      setDefinitions(await fetchReportDefinitions(false))
    } catch (error) {
      setDefinitionError(
        error instanceof Error ? error.message : "Failed to load definitions.",
      )
      setDefinitions([])
    } finally {
      setLoadingDefinitions(false)
    }
  }, [])

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true)
    setRunError(null)
    try {
      setRuns(await fetchReportRuns({ limit: 50 }))
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Failed to load runs.")
      setRuns([])
    } finally {
      setLoadingRuns(false)
    }
  }, [])

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

  useEffect(() => {
    void loadDefinitions()
    void loadRuns()
  }, [loadDefinitions, loadRuns])

  useEffect(() => {
    const hasActive = runs.some((run) => activeRunStatuses.includes(run.status))
    if (activeTab !== "runs" || !hasActive) return
    const intervalId = window.setInterval(() => {
      void loadRuns()
    }, 5000)
    return () => window.clearInterval(intervalId)
  }, [activeTab, loadRuns, runs])

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
      if (formState.periodStart && formState.periodEnd && formState.periodEnd < formState.periodStart) {
        return setSheetError("Period End must be on or after Period Start."), false
      }
      if (formState.amountMin && !decimalPattern.test(formState.amountMin.trim())) {
        return setSheetError("Amount Min must be a decimal string."), false
      }
      if (formState.amountMax && !decimalPattern.test(formState.amountMax.trim())) {
        return setSheetError("Amount Max must be a decimal string."), false
      }
    }
    if (targetStep === 4 && formState.sortField && !formState.metricKeys.includes(formState.sortField)) {
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
      export_formats: formState.exportFormats,
      config: parsedConfig,
    }

    setSavingDefinition(true)
    try {
      if (sheetMode === "edit" && editingDefinitionId) {
        await updateReportDefinition(editingDefinitionId, body)
      } else {
        await createReportDefinition(body)
      }
      await loadDefinitions()
      setActiveTab("definitions")
      closeSheet()
    } catch (error) {
      setSheetError(error instanceof Error ? error.message : "Save failed.")
    } finally {
      setSavingDefinition(false)
    }
  }

  const deleteDefinitionAction = async (id: string) => {
    if (!window.confirm("Delete this definition? This performs a soft delete.")) return
    try {
      await deleteReportDefinition(id)
      await loadDefinitions()
    } catch (error) {
      setDefinitionError(error instanceof Error ? error.message : "Delete failed.")
    }
  }

  const runDefinitionAction = async (id: string) => {
    setRunningDefinitionId(id)
    try {
      await runReport(id)
      setActiveTab("runs")
      await loadRuns()
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Run failed.")
    } finally {
      setRunningDefinitionId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Custom Reports</h1>
          <p className="text-sm text-muted-foreground">
            Define reusable metric reports and run them on demand.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => {
            void openCreateSheet()
          }}
        >
          New Report
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className={cn(
            "rounded-md border px-3 py-1.5 text-sm",
            activeTab === "runs"
              ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
          onClick={() => setActiveTab("runs")}
        >
          Runs
        </button>
        <button
          type="button"
          className={cn(
            "rounded-md border px-3 py-1.5 text-sm",
            activeTab === "definitions"
              ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
          onClick={() => setActiveTab("definitions")}
        >
          Definitions
        </button>
      </div>

      {activeTab === "runs" ? (
        <section className="rounded-lg border border-border bg-card p-4">
          {runError ? (
            <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {runError}
            </p>
          ) : null}

          {loadingRuns ? (
            <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
          ) : null}

          {!loadingRuns && !runs.length ? (
            <p className="rounded-md border border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
              No runs yet. Run your first report.
            </p>
          ) : null}

          {!!runs.length ? (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Report Name
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Status
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Rows
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Started
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Completed
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.id} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">
                        {definitionNameById.get(run.definition_id) ?? run.definition_id}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                            statusClassMap[run.status],
                            run.status === ReportRunStatus.RUNNING ? "animate-pulse" : "",
                          )}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {run.row_count ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {formatDateTime(run.started_at)}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {formatDateTime(run.completed_at)}
                      </td>
                      <td className="px-3 py-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => router.push(`/reports/${run.id}`)}
                        >
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="rounded-lg border border-border bg-card p-4">
          {definitionError ? (
            <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {definitionError}
            </p>
          ) : null}
          {loadingDefinitions ? (
            <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
          ) : null}
          {!loadingDefinitions && !definitions.length ? (
            <p className="rounded-md border border-border bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
              No report definitions yet.
            </p>
          ) : null}
          {!!definitions.length ? (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">Name</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Metrics</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Filters</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Formats</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Active</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {definitions.map((definition) => {
                    const filterCount =
                      definition.filter_config.conditions.length +
                      (definition.filter_config.period_start ? 1 : 0) +
                      (definition.filter_config.period_end ? 1 : 0) +
                      definition.filter_config.entity_ids.length +
                      definition.filter_config.tags.length
                    return (
                      <tr key={definition.id} className="border-t border-border">
                        <td className="px-3 py-2 text-muted-foreground">{definition.name}</td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {definition.metric_keys.length}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">{filterCount}</td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {definition.export_formats.join(", ")}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={cn(
                              "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                              definition.is_active
                                ? "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
                                : "bg-muted text-muted-foreground",
                            )}
                          >
                            {definition.is_active ? "Yes" : "No"}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                void runDefinitionAction(definition.id)
                              }}
                              disabled={
                                !definition.is_active ||
                                runningDefinitionId === definition.id
                              }
                            >
                              {runningDefinitionId === definition.id ? (
                                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Play className="mr-1 h-3.5 w-3.5" />
                              )}
                              Run
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                void openEditSheet(definition)
                              }}
                            >
                              <Pencil className="mr-1 h-3.5 w-3.5" />
                              Edit
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                void deleteDefinitionAction(definition.id)
                              }}
                            >
                              <Trash2 className="mr-1 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      )}
      {sheetMode ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60">
          <aside className="h-full w-full max-w-2xl overflow-y-auto border-l border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                {sheetMode === "create" ? "Create Report" : "Edit Report"}
              </h2>
              <Button
                type="button"
                variant="outline"
                onClick={closeSheet}
                disabled={savingDefinition}
              >
                Close
              </Button>
            </div>

            <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
              {[1, 2, 3, 4].map((item) => (
                <span
                  key={item}
                  className={cn(
                    "rounded-full border px-2 py-1",
                    step === item
                      ? "border-[hsl(var(--brand-primary))] text-foreground"
                      : "border-border",
                  )}
                >
                  Step {item}
                </span>
              ))}
            </div>

            <div className="mt-4 space-y-4">
              {step === 1 ? (
                <>
                  <div className="space-y-1">
                    <label className="text-sm text-foreground" htmlFor="report-name">
                      Name
                    </label>
                    <Input
                      id="report-name"
                      value={formState.name}
                      onChange={(event) => setForm({ name: event.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm text-foreground" htmlFor="report-description">
                      Description
                    </label>
                    <textarea
                      id="report-description"
                      className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                      value={formState.description}
                      onChange={(event) => setForm({ description: event.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm text-foreground">Export Formats</p>
                    <div className="grid gap-2 sm:grid-cols-3">
                      {exportFormatOptions.map((format) => (
                        <label
                          key={format}
                          className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                        >
                          <input
                            type="checkbox"
                            checked={formState.exportFormats.includes(format)}
                            onChange={(event) =>
                              setForm({
                                exportFormats: event.target.checked
                                  ? Array.from(
                                      new Set([...formState.exportFormats, format]),
                                    )
                                  : formState.exportFormats.filter((item) => item !== format),
                              })
                            }
                          />
                          {format}
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              ) : null}

              {step === 2 ? (
                <>
                  {loadingMetrics ? (
                    <div className="h-24 animate-pulse rounded-md border border-border bg-muted/20" />
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {formState.metricKeys.map((metricKey) => (
                      <span
                        key={metricKey}
                        className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                      >
                        {metricByKey.get(metricKey)?.label ?? metricKey}
                        <button
                          type="button"
                          className="text-foreground"
                          onClick={() =>
                            setForm({
                              metricKeys: formState.metricKeys.filter((item) => item !== metricKey),
                              groupBy: formState.groupBy.filter((item) => item !== metricKey),
                              sortField:
                                formState.sortField === metricKey ? "" : formState.sortField,
                            })
                          }
                        >
                          x
                        </button>
                      </span>
                    ))}
                  </div>
                  {groupedMetrics.map(([engine, engineMetrics]) => (
                    <details
                      key={engine}
                      className="rounded-md border border-border bg-background/30"
                      open
                    >
                      <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-foreground">
                        {engine}
                      </summary>
                      <div className="space-y-2 border-t border-border px-3 py-3">
                        {engineMetrics.map((metric) => (
                          <label
                            key={metric.key}
                            className="flex items-center gap-2 text-sm text-muted-foreground"
                          >
                            <input
                              type="checkbox"
                              checked={formState.metricKeys.includes(metric.key)}
                              onChange={(event) =>
                                setForm({
                                  metricKeys: event.target.checked
                                    ? Array.from(
                                        new Set([...formState.metricKeys, metric.key]),
                                      )
                                    : formState.metricKeys.filter((item) => item !== metric.key),
                                })
                              }
                            />
                            <span className="text-foreground">{metric.label}</span>
                            <span className="text-xs">({metric.key})</span>
                          </label>
                        ))}
                      </div>
                    </details>
                  ))}
                </>
              ) : null}

              {step === 3 ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="period-start">
                        Period Start
                      </label>
                      <Input
                        id="period-start"
                        type="date"
                        value={formState.periodStart}
                        onChange={(event) => setForm({ periodStart: event.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="period-end">
                        Period End
                      </label>
                      <Input
                        id="period-end"
                        type="date"
                        value={formState.periodEnd}
                        onChange={(event) => setForm({ periodEnd: event.target.value })}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm text-foreground">Entity IDs (comma-separated UUIDs)</p>
                    <div className="flex gap-2">
                      <Input
                        value={formState.entityInput}
                        onChange={(event) => setForm({ entityInput: event.target.value })}
                        placeholder="uuid1, uuid2"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => {
                          const values = parseCommaSeparated(formState.entityInput)
                          if (!values.length) return
                          const invalid = values.find((value) => !uuidPattern.test(value))
                          if (invalid) {
                            setSheetError(`Invalid entity UUID: ${invalid}`)
                            return
                          }
                          setForm({
                            entityIds: Array.from(
                              new Set([...formState.entityIds, ...values]),
                            ),
                            entityInput: "",
                          })
                          setSheetError(null)
                        }}
                      >
                        Add
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {formState.entityIds.map((entityId) => (
                        <span
                          key={entityId}
                          className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                        >
                          {entityId}
                          <button
                            type="button"
                            className="text-foreground"
                            onClick={() =>
                              setForm({
                                entityIds: formState.entityIds.filter((value) => value !== entityId),
                              })
                            }
                          >
                            x
                          </button>
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="amount-min">
                        Amount Min (decimal string)
                      </label>
                      <Input
                        id="amount-min"
                        value={formState.amountMin}
                        onChange={(event) => setForm({ amountMin: event.target.value })}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="amount-max">
                        Amount Max (decimal string)
                      </label>
                      <Input
                        id="amount-max"
                        value={formState.amountMax}
                        onChange={(event) => setForm({ amountMax: event.target.value })}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm text-foreground">Tags (comma-separated)</p>
                    <div className="flex gap-2">
                      <Input
                        value={formState.tagsInput}
                        onChange={(event) => setForm({ tagsInput: event.target.value })}
                        placeholder="finance, board"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() =>
                          setForm({
                            tags: Array.from(
                              new Set([
                                ...formState.tags,
                                ...parseCommaSeparated(formState.tagsInput),
                              ]),
                            ),
                            tagsInput: "",
                          })
                        }
                      >
                        Add
                      </Button>
                    </div>
                  </div>
                </>
              ) : null}

              {step === 4 ? (
                <>
                  <div className="space-y-2">
                    <p className="text-sm text-foreground">Group By</p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {formState.metricKeys.map((metricKey) => (
                        <label
                          key={metricKey}
                          className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                        >
                          <input
                            type="checkbox"
                            checked={formState.groupBy.includes(metricKey)}
                            onChange={(event) =>
                              setForm({
                                groupBy: event.target.checked
                                  ? Array.from(
                                      new Set([...formState.groupBy, metricKey]),
                                    )
                                  : formState.groupBy.filter((item) => item !== metricKey),
                              })
                            }
                          />
                          {metricByKey.get(metricKey)?.label ?? metricKey}
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="sort-field">
                        Sort Field
                      </label>
                      <select
                        id="sort-field"
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={formState.sortField}
                        onChange={(event) => setForm({ sortField: event.target.value })}
                      >
                        <option value="">None</option>
                        {formState.metricKeys.map((metricKey) => (
                          <option key={metricKey} value={metricKey}>
                            {metricByKey.get(metricKey)?.label ?? metricKey}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="text-sm text-foreground" htmlFor="sort-direction">
                        Sort Direction
                      </label>
                      <select
                        id="sort-direction"
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                        value={formState.sortDirection}
                        onChange={(event) =>
                          setForm({
                            sortDirection:
                              event.target.value === SortDirection.DESC
                                ? SortDirection.DESC
                                : SortDirection.ASC,
                          })
                        }
                      >
                        <option value={SortDirection.ASC}>ASC</option>
                        <option value={SortDirection.DESC}>DESC</option>
                      </select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm text-foreground" htmlFor="config-text">
                      Config (JSON)
                    </label>
                    <textarea
                      id="config-text"
                      className="min-h-32 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
                      value={formState.configText}
                      onChange={(event) => setForm({ configText: event.target.value })}
                    />
                  </div>
                </>
              ) : null}

              {sheetError ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {sheetError}
                </p>
              ) : null}
            </div>

            <div className="mt-5 flex items-center justify-between gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep((previous) => Math.max(previous - 1, 1))}
                disabled={savingDefinition || step === 1}
              >
                Back
              </Button>
              {step < 4 ? (
                <Button
                  type="button"
                  onClick={() => {
                    if (!validateStep(step)) return
                    setStep((previous) => Math.min(previous + 1, 4))
                  }}
                  disabled={savingDefinition}
                >
                  Next
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={() => {
                    void saveDefinition()
                  }}
                  disabled={savingDefinition}
                >
                  {savingDefinition ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save"
                  )}
                </Button>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
