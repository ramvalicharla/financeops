"use client"

import { useCallback, useMemo, useState } from "react"
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
import { useAsyncAction, useFetch, usePolling } from "@/hooks"

export type ActiveBoardPackTab = "runs" | "definitions"
type ConfirmState = {
  open: boolean
  title: string
  description: string
  variant: "default" | "destructive"
  onConfirm: () => void
}

export interface EditDefinitionState {
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

export const allSectionTypes = Object.values(SectionType)

const toDateInput = (value: Date): string => value.toISOString().slice(0, 10)

const currentMonthStart = (): string => {
  const now = new Date()
  return toDateInput(new Date(now.getFullYear(), now.getMonth(), 1))
}

const currentMonthEnd = (): string => {
  const now = new Date()
  return toDateInput(new Date(now.getFullYear(), now.getMonth() + 1, 0))
}

export const truncate = (
  value: string | null | undefined,
  length: number,
): string => {
  if (!value) {
    return "-"
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

export function useBoardPack() {
  const [activeTab, setActiveTab] = useState<ActiveBoardPackTab>("runs")
  const [definitionActionError, setDefinitionActionError] = useState<string | null>(
    null,
  )
  const [runActionError, setRunActionError] = useState<string | null>(null)

  const [generateOpen, setGenerateOpen] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [generateDefinitionId, setGenerateDefinitionId] = useState("")
  const [generatePeriodStart, setGeneratePeriodStart] = useState(currentMonthStart())
  const [generatePeriodEnd, setGeneratePeriodEnd] = useState(currentMonthEnd())

  const [editState, setEditState] = useState<EditDefinitionState | null>(null)
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null)

  const definitionsQuery = useFetch(() => fetchDefinitions(false), [])
  const runsQuery = useFetch(() => fetchRuns({ limit: 50 }), [])

  const definitions = useMemo(() => definitionsQuery.data ?? [], [definitionsQuery.data])
  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data])
  const loadingDefinitions = definitionsQuery.isLoading
  const loadingRuns = runsQuery.isLoading
  const definitionError =
    definitionActionError ?? definitionsQuery.error?.message ?? null
  const runError = runActionError ?? runsQuery.error?.message ?? null

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
    setDefinitionActionError(null)
    await definitionsQuery.refetch()
  }, [definitionsQuery])

  const loadRuns = useCallback(async () => {
    setRunActionError(null)
    await runsQuery.refetch()
  }, [runsQuery])

  usePolling(
    async () => {
      await loadRuns()
    },
    5000,
    activeTab === "runs" && hasActiveRuns,
  )

  const generateAction = useAsyncAction(async () => {
    await generatePack({
      definition_id: generateDefinitionId,
      period_start: generatePeriodStart,
      period_end: generatePeriodEnd,
    })
    closeGenerateDialog()
    setActiveTab("runs")
    await loadRuns()
  })

  const saveEditAction = useAsyncAction(
    async (payload: {
      id: string
      name: string
      description: string | null
      sectionTypes: SectionType[]
      entityIds: string[]
      config: Record<string, unknown>
    }) => {
      await updateDefinition(payload.id, {
        name: payload.name,
        description: payload.description,
        section_types: payload.sectionTypes,
        entity_ids: payload.entityIds,
        config: payload.config,
      })
      await loadDefinitions()
      closeEditSheet()
    },
  )

  const deleteDefinitionActionState = useAsyncAction(async (definitionId: string) => {
    await deleteDefinition(definitionId)
    await loadDefinitions()
  })

  const openGenerateDialog = (definitionId?: string) => {
    setGenerateDefinitionId(definitionId ?? "")
    setGeneratePeriodStart(currentMonthStart())
    setGeneratePeriodEnd(currentMonthEnd())
    setGenerateError(null)
    setGenerateOpen(true)
  }

  const closeGenerateDialog = () => {
    setGenerateOpen(false)
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
    setGenerateError(null)
    try {
      setRunActionError(null)
      await generateAction.execute()
    } catch (error) {
      setGenerateError(error instanceof Error ? error.message : "Generate failed.")
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

  const closeEditSheet = () => {
    setEditState(null)
  }

  const dismissConfirm = useCallback(() => {
    setConfirmState(null)
  }, [])

  const setEditValue = (updates: Partial<EditDefinitionState>) => {
    setEditState((previous) => (previous ? { ...previous, ...updates } : previous))
  }

  const addEntityId = () => {
    setEditState((previous) => {
      if (!previous) return previous
      const candidate = previous.newEntityId.trim()
      if (!isValidUuid(candidate) || previous.entityIds.includes(candidate)) {
        return {
          ...previous,
          error: "Entity ID must be a unique UUID.",
        }
      }
      return {
        ...previous,
        entityIds: [...previous.entityIds, candidate],
        newEntityId: "",
        error: null,
      }
    })
  }

  const removeEntityId = (entityId: string) => {
    setEditState((previous) =>
      previous
        ? {
            ...previous,
            entityIds: previous.entityIds.filter((value) => value !== entityId),
          }
        : previous,
    )
  }

  const toggleSectionType = (sectionType: SectionType, checked: boolean) => {
    setEditState((previous) => {
      if (!previous) {
        return previous
      }
      const next = checked
        ? [...previous.sectionTypes, sectionType]
        : previous.sectionTypes.filter((value) => value !== sectionType)
      return { ...previous, sectionTypes: next }
    })
  }

  const handleSaveEdit = async () => {
    if (!editState) {
      return
    }
    if (!editState.name.trim()) {
      return setEditValue({ error: "Name is required." })
    }
    if (!editState.sectionTypes.length) {
      return setEditValue({ error: "Select at least one section type." })
    }
    if (!editState.entityIds.length) {
      return setEditValue({ error: "Add at least one entity ID." })
    }

    let parsedConfig: Record<string, unknown>
    try {
      const parsed = JSON.parse(editState.configText || "{}")
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        parsedConfig = parsed as Record<string, unknown>
      } else {
        setEditValue({ error: "Config must be a JSON object." })
        return
      }
    } catch {
      setEditValue({ error: "Config JSON is invalid." })
      return
    }

    setEditState((previous) =>
      previous ? { ...previous, saving: true, error: null } : previous,
    )

    try {
      await saveEditAction.execute({
        id: editState.id,
        name: editState.name.trim(),
        description: editState.description.trim() || null,
        sectionTypes: editState.sectionTypes,
        entityIds: editState.entityIds,
        config: parsedConfig,
      })
    } catch (error) {
      setEditState((previous) =>
        previous
          ? {
              ...previous,
              saving: false,
              error: error instanceof Error ? error.message : "Update failed.",
            }
          : previous,
      )
      return
    }

    setEditState((previous) =>
      previous ? { ...previous, saving: false } : previous,
    )
  }

  const handleDeleteDefinition = async (definitionId: string) => {
    setConfirmState({
      open: true,
      title: "Delete board pack",
      description:
        "This will permanently delete the board pack definition and all associated run history. This cannot be undone.",
      variant: "destructive",
      onConfirm: () => {
        void (async () => {
          try {
            setDefinitionActionError(null)
            await deleteDefinitionActionState.execute(definitionId)
          } catch (error) {
            setDefinitionActionError(
              error instanceof Error ? error.message : "Delete action failed.",
            )
          } finally {
            dismissConfirm()
          }
        })()
      },
    })
  }

  return {
    activeDefinitions,
    activeTab,
    closeEditSheet,
    closeGenerateDialog,
    confirmLoading: deleteDefinitionActionState.isLoading,
    confirmState,
    definitionError,
    definitionNameById,
    definitions,
    dismissConfirm,
    editState,
    generateDefinitionId,
    generateError,
    generateOpen,
    generatePeriodEnd,
    generatePeriodStart,
    generateSubmitting: generateAction.isLoading,
    handleDeleteDefinition,
    handleGenerate,
    handleSaveEdit,
    loadRuns,
    loadingDefinitions,
    loadingRuns,
    openEditSheet,
    openGenerateDialog,
    runError,
    runs,
    setActiveTab,
    setEditValue,
    setGenerateDefinitionId,
    setGeneratePeriodEnd,
    setGeneratePeriodStart,
    toggleSectionType,
    addEntityId,
    removeEntityId,
  }
}
