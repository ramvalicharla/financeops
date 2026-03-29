"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Pencil, Play, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  deleteDefinition,
  fetchDefinitions,
  fetchRuns,
  generatePack,
  updateDefinition,
} from "@/lib/api/board-pack"
import {
  type DefinitionResponse,
  PackRunStatus,
  type RunResponse,
  SectionType,
} from "@/lib/types/board-pack"
import { cn } from "@/lib/utils"

type ActiveTab = "runs" | "definitions"

interface EditDefinitionState {
  id: string
  name: string
  description: string
  sectionTypes: SectionType[]
  entityIds: string[]
  newEntityId: string
  configText: string
  saving: boolean
  error: string | null
}

const activeRunStatuses: PackRunStatus[] = [
  PackRunStatus.PENDING,
  PackRunStatus.RUNNING,
]

const statusClassMap: Record<PackRunStatus, string> = {
  [PackRunStatus.PENDING]: "bg-yellow-500/20 text-yellow-300",
  [PackRunStatus.RUNNING]: "bg-blue-500/20 text-blue-300",
  [PackRunStatus.COMPLETE]:
    "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  [PackRunStatus.FAILED]:
    "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
}

const allSectionTypes = Object.values(SectionType)

const toDateInput = (value: Date): string => value.toISOString().slice(0, 10)

const currentMonthStart = (): string => {
  const now = new Date()
  return toDateInput(new Date(now.getFullYear(), now.getMonth(), 1))
}

const currentMonthEnd = (): string => {
  const now = new Date()
  return toDateInput(new Date(now.getFullYear(), now.getMonth() + 1, 0))
}

const truncate = (value: string | null | undefined, length: number): string => {
  if (!value) {
    return "—"
  }
  if (value.length <= length) {
    return value
  }
  return `${value.slice(0, length)}...`
}

const isValidUuid = (value: string): boolean =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  )

export default function BoardPackPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<ActiveTab>("runs")
  const [definitions, setDefinitions] = useState<DefinitionResponse[]>([])
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loadingDefinitions, setLoadingDefinitions] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [definitionError, setDefinitionError] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  const [generateOpen, setGenerateOpen] = useState(false)
  const [generateSubmitting, setGenerateSubmitting] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [generateDefinitionId, setGenerateDefinitionId] = useState("")
  const [generatePeriodStart, setGeneratePeriodStart] = useState(currentMonthStart())
  const [generatePeriodEnd, setGeneratePeriodEnd] = useState(currentMonthEnd())

  const [editState, setEditState] = useState<EditDefinitionState | null>(null)

  const definitionNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const definition of definitions) {
      map.set(definition.id, definition.name)
    }
    return map
  }, [definitions])

  const activeDefinitions = useMemo(
    () => definitions.filter((definition) => definition.is_active),
    [definitions],
  )

  const hasActiveRuns = useMemo(
    () => runs.some((run) => activeRunStatuses.includes(run.status)),
    [runs],
  )

  const loadDefinitions = useCallback(async () => {
    setLoadingDefinitions(true)
    setDefinitionError(null)
    try {
      const response = await fetchDefinitions(false)
      setDefinitions(response)
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
      const response = await fetchRuns({ limit: 50 })
      setRuns(response)
    } catch (error) {
      setRunError(error instanceof Error ? error.message : "Failed to load runs.")
      setRuns([])
    } finally {
      setLoadingRuns(false)
    }
  }, [])

  useEffect(() => {
    void loadDefinitions()
    void loadRuns()
  }, [loadDefinitions, loadRuns])

  useEffect(() => {
    if (activeTab !== "runs" || !hasActiveRuns) {
      return
    }
    const intervalId = window.setInterval(() => {
      void loadRuns()
    }, 5000)
    return () => {
      window.clearInterval(intervalId)
    }
  }, [activeTab, hasActiveRuns, loadRuns])

  const openGenerateModal = (definitionId?: string) => {
    setGenerateDefinitionId(definitionId ?? "")
    setGeneratePeriodStart(currentMonthStart())
    setGeneratePeriodEnd(currentMonthEnd())
    setGenerateError(null)
    setGenerateOpen(true)
  }

  const handleGenerate = async () => {
    if (!generateDefinitionId) {
      setGenerateError("Select a definition.")
      return
    }
    if (!generatePeriodStart || !generatePeriodEnd) {
      setGenerateError("Both period dates are required.")
      return
    }
    if (generatePeriodEnd < generatePeriodStart) {
      setGenerateError("Period End must be on or after Period Start.")
      return
    }
    setGenerateSubmitting(true)
    setGenerateError(null)
    try {
      await generatePack({
        definition_id: generateDefinitionId,
        period_start: generatePeriodStart,
        period_end: generatePeriodEnd,
      })
      setGenerateOpen(false)
      setActiveTab("runs")
      await loadRuns()
    } catch (error) {
      setGenerateError(error instanceof Error ? error.message : "Generate failed.")
    } finally {
      setGenerateSubmitting(false)
    }
  }

  const openEditSheet = (definition: DefinitionResponse) => {
    setEditState({
      id: definition.id,
      name: definition.name,
      description: definition.description ?? "",
      sectionTypes: definition.section_types
        .filter((value): value is SectionType =>
          allSectionTypes.includes(value as SectionType),
        )
        .map((value) => value as SectionType),
      entityIds: [...definition.entity_ids],
      newEntityId: "",
      configText: JSON.stringify(definition.config ?? {}, null, 2),
      saving: false,
      error: null,
    })
  }

  const handleSaveEdit = async () => {
    if (!editState) {
      return
    }
    if (!editState.name.trim()) {
      setEditState((prev) => (prev ? { ...prev, error: "Name is required." } : prev))
      return
    }
    if (!editState.sectionTypes.length) {
      setEditState((prev) =>
        prev ? { ...prev, error: "Select at least one section type." } : prev,
      )
      return
    }
    if (!editState.entityIds.length) {
      setEditState((prev) =>
        prev ? { ...prev, error: "Add at least one entity ID." } : prev,
      )
      return
    }

    let parsedConfig: Record<string, unknown>
    try {
      const parsed = JSON.parse(editState.configText || "{}")
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        parsedConfig = parsed as Record<string, unknown>
      } else {
        setEditState((prev) =>
          prev ? { ...prev, error: "Config must be a JSON object." } : prev,
        )
        return
      }
    } catch {
      setEditState((prev) =>
        prev ? { ...prev, error: "Config JSON is invalid." } : prev,
      )
      return
    }

    setEditState((prev) => (prev ? { ...prev, saving: true, error: null } : prev))
    try {
      await updateDefinition(editState.id, {
        name: editState.name.trim(),
        description: editState.description.trim() || null,
        section_types: editState.sectionTypes,
        entity_ids: editState.entityIds,
        config: parsedConfig,
      })
      await loadDefinitions()
      setEditState(null)
    } catch (error) {
      setEditState((prev) =>
        prev
          ? {
              ...prev,
              saving: false,
              error: error instanceof Error ? error.message : "Update failed.",
            }
          : prev,
      )
      return
    }
    setEditState((prev) => (prev ? { ...prev, saving: false } : prev))
  }

  const handleDeleteDefinition = async (definitionId: string) => {
    const confirmed = window.confirm(
      "Delete this definition? This will deactivate it (soft delete).",
    )
    if (!confirmed) {
      return
    }
    try {
      await deleteDefinition(definitionId)
      await loadDefinitions()
    } catch (error) {
      setDefinitionError(
        error instanceof Error ? error.message : "Delete action failed.",
      )
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Board Packs</h1>
          <p className="text-sm text-muted-foreground">
            Generate and review period board-pack outputs.
          </p>
        </div>
        <Button type="button" onClick={() => openGenerateModal()}>
          New Pack
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
              No runs yet. Generate your first board pack.
            </p>
          ) : null}

          {!!runs.length ? (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">Period</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Definition
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Status</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Chain Hash
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Generated
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
                        {run.period_start} to {run.period_end}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {definitionNameById.get(run.definition_id) ?? run.definition_id}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                            statusClassMap[run.status],
                            run.status === PackRunStatus.RUNNING
                              ? "animate-pulse"
                              : "",
                          )}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                        {truncate(run.chain_hash, 16)}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {new Date(run.completed_at ?? run.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => router.push(`/board-pack/${run.id}`)}
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
              No definitions yet.
            </p>
          ) : null}

          {!!definitions.length ? (
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full min-w-[980px] text-sm">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="px-3 py-2 text-left font-medium text-foreground">Name</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Period Type
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Sections
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Entities
                    </th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">Active</th>
                    <th className="px-3 py-2 text-left font-medium text-foreground">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {definitions.map((definition) => (
                    <tr key={definition.id} className="border-t border-border">
                      <td className="px-3 py-2 text-muted-foreground">{definition.name}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {definition.period_type}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {definition.section_types.length}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {definition.entity_ids.length}
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
                            onClick={() => openEditSheet(definition)}
                          >
                            <Pencil className="mr-1 h-3.5 w-3.5" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => openGenerateModal(definition.id)}
                            disabled={!definition.is_active}
                          >
                            <Play className="mr-1 h-3.5 w-3.5" />
                            Generate
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              void handleDeleteDefinition(definition.id)
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
      )}

      {generateOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-5">
            <h2 className="text-lg font-semibold text-foreground">Generate Board Pack</h2>
            <div className="mt-4 space-y-3">
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="generate-definition">
                  Definition
                </label>
                <select
                  id="generate-definition"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={generateDefinitionId}
                  onChange={(event) => setGenerateDefinitionId(event.target.value)}
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
                    value={generatePeriodStart}
                    onChange={(event) => setGeneratePeriodStart(event.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm text-foreground" htmlFor="generate-period-end">
                    Period End
                  </label>
                  <Input
                    id="generate-period-end"
                    type="date"
                    value={generatePeriodEnd}
                    onChange={(event) => setGeneratePeriodEnd(event.target.value)}
                  />
                </div>
              </div>

              {generateError ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {generateError}
                </p>
              ) : null}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setGenerateOpen(false)}
                disabled={generateSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  void handleGenerate()
                }}
                disabled={generateSubmitting}
              >
                {generateSubmitting ? (
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
        </div>
      ) : null}

      {editState ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60">
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">Edit Definition</h2>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditState(null)}
                disabled={editState.saving}
              >
                Close
              </Button>
            </div>

            <div className="mt-4 space-y-4">
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="edit-name">
                  Name
                </label>
                <Input
                  id="edit-name"
                  value={editState.name}
                  onChange={(event) =>
                    setEditState((prev) =>
                      prev ? { ...prev, name: event.target.value } : prev,
                    )
                  }
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="edit-description">
                  Description
                </label>
                <textarea
                  id="edit-description"
                  className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  value={editState.description}
                  onChange={(event) =>
                    setEditState((prev) =>
                      prev ? { ...prev, description: event.target.value } : prev,
                    )
                  }
                />
              </div>

              <div className="space-y-2">
                <p className="text-sm text-foreground">Section Types</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {allSectionTypes.map((sectionType) => {
                    const checked = editState.sectionTypes.includes(sectionType)
                    return (
                      <label
                        key={sectionType}
                        className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(event) => {
                            setEditState((prev) => {
                              if (!prev) {
                                return prev
                              }
                              const next = event.target.checked
                                ? [...prev.sectionTypes, sectionType]
                                : prev.sectionTypes.filter(
                                    (value) => value !== sectionType,
                                  )
                              return { ...prev, sectionTypes: next }
                            })
                          }}
                        />
                        {sectionType}
                      </label>
                    )
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm text-foreground">Entity IDs</p>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add entity UUID"
                    value={editState.newEntityId}
                    onChange={(event) =>
                      setEditState((prev) =>
                        prev ? { ...prev, newEntityId: event.target.value } : prev,
                      )
                    }
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setEditState((prev) => {
                        if (!prev) {
                          return prev
                        }
                        const candidate = prev.newEntityId.trim()
                        if (!isValidUuid(candidate) || prev.entityIds.includes(candidate)) {
                          return {
                            ...prev,
                            error: "Entity ID must be a unique UUID.",
                          }
                        }
                        return {
                          ...prev,
                          entityIds: [...prev.entityIds, candidate],
                          newEntityId: "",
                          error: null,
                        }
                      })
                    }}
                  >
                    Add
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {editState.entityIds.map((entityId) => (
                    <span
                      key={entityId}
                      className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                    >
                      {entityId}
                      <button
                        type="button"
                        className="text-foreground"
                        onClick={() => {
                          setEditState((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  entityIds: prev.entityIds.filter(
                                    (value) => value !== entityId,
                                  ),
                                }
                              : prev,
                          )
                        }}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-sm text-foreground" htmlFor="edit-config">
                  Config (JSON)
                </label>
                <textarea
                  id="edit-config"
                  className="min-h-40 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
                  value={editState.configText}
                  onChange={(event) =>
                    setEditState((prev) =>
                      prev ? { ...prev, configText: event.target.value } : prev,
                    )
                  }
                />
              </div>

              {editState.error ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {editState.error}
                </p>
              ) : null}
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditState(null)}
                disabled={editState.saving}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  void handleSaveEdit()
                }}
                disabled={editState.saving}
              >
                {editState.saving ? (
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
      ) : null}
    </div>
  )
}
