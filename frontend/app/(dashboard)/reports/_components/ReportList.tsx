"use client"

import { useRouter } from "next/navigation"
import { Loader2, Pencil, Play, Trash2 } from "lucide-react"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Button } from "@/components/ui/button"
import type {
  ReportDefinitionResponse,
  ReportRunResponse,
} from "@/lib/types/report-builder"
import { formatDateTime } from "../_hooks/useReports"

interface ReportRunsListProps {
  mode: "runs"
  definitionNameById: Map<string, string>
  error: string | null
  loading: boolean
  runs: ReportRunResponse[]
}

interface ReportDefinitionsListProps {
  mode: "definitions"
  definitions: ReportDefinitionResponse[]
  error: string | null
  loading: boolean
  onDelete: (definitionId: string) => void
  onEdit: (definition: ReportDefinitionResponse) => void
  onRun: (definition: ReportDefinitionResponse) => void
  runningDefinitionId: string | null
}

type ReportListProps = ReportRunsListProps | ReportDefinitionsListProps

export function ReportList(props: ReportListProps) {
  const router = useRouter()

  if (props.mode === "runs") {
    const { definitionNameById, error, loading, runs } = props

    return (
      <section className="rounded-lg border border-border bg-card p-4">
        {error ? (
          <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {loading ? (
          <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
        ) : null}

        {!loading && !runs.length ? (
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
                      <StatusBadge status={run.status} />
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
    )
  }

  const {
    definitions,
    error,
    loading,
    onDelete,
    onEdit,
    onRun,
    runningDefinitionId,
  } = props

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      {error ? (
        <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {loading ? (
        <div className="h-32 animate-pulse rounded-md border border-border bg-muted/30" />
      ) : null}
      {!loading && !definitions.length ? (
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
                      <StatusBadge
                        status={definition.is_active ? "active" : "draft"}
                        label={definition.is_active ? "Yes" : "No"}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => onRun(definition)}
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
                          onClick={() => onEdit(definition)}
                        >
                          <Pencil className="mr-1 h-3.5 w-3.5" />
                          Edit
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => onDelete(definition.id)}
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
  )
}
