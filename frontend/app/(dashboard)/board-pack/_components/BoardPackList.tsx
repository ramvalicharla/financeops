"use client"

import { useRouter } from "next/navigation"
import { Pencil, Play, Trash2 } from "lucide-react"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { Button } from "@/components/ui/button"
import type { DefinitionResponse, RunResponse } from "@/lib/types/board-pack"
import { truncate } from "../_hooks/useBoardPack"

interface BoardPackRunsListProps {
  mode: "runs"
  definitionNameById: Map<string, string>
  error: string | null
  loading: boolean
  runs: RunResponse[]
}

interface BoardPackDefinitionsListProps {
  mode: "definitions"
  definitions: DefinitionResponse[]
  error: string | null
  loading: boolean
  onDelete: (definitionId: string) => void
  onEdit: (definition: DefinitionResponse) => void
  onGenerate: (definitionId?: string) => void
}

type BoardPackListProps = BoardPackRunsListProps | BoardPackDefinitionsListProps

export function BoardPackList(props: BoardPackListProps) {
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
                      <StatusBadge status={run.status} />
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
    )
  }

  const { definitions, error, loading, onDelete, onEdit, onGenerate } = props

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
                        onClick={() => onEdit(definition)}
                      >
                        <Pencil className="mr-1 h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => onGenerate(definition.id)}
                        disabled={!definition.is_active}
                      >
                        <Play className="mr-1 h-3.5 w-3.5" />
                        Generate
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
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
