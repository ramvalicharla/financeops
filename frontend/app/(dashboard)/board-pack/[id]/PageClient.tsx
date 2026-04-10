"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Download, Loader2 } from "lucide-react"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { Button } from "@/components/ui/button"
import {
  downloadArtifact,
  fetchArtifacts,
  fetchDefinitions,
  fetchRun,
  fetchSections,
} from "@/lib/api/board-pack"
import type {
  ArtifactResponse,
  PackRunStatus,
  RunResponse,
  SectionResponse,
} from "@/lib/types/board-pack"
import { PackRunStatus as PackRunStatusEnum } from "@/lib/types/board-pack"
import { cn } from "@/lib/utils"

const statusClassMap: Record<PackRunStatus, string> = {
  [PackRunStatusEnum.PENDING]: "bg-yellow-500/20 text-yellow-300",
  [PackRunStatusEnum.RUNNING]: "bg-blue-500/20 text-blue-300",
  [PackRunStatusEnum.COMPLETE]:
    "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  [PackRunStatusEnum.FAILED]:
    "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
}

const truncate = (value: string | null | undefined, length: number): string => {
  if (!value) {
    return "â€”"
  }
  if (value.length <= length) {
    return value
  }
  return `${value.slice(0, length)}...`
}

const formatBytes = (value: number | null): string => {
  if (!value || value <= 0) {
    return "â€”"
  }
  if (value < 1024) {
    return `${value} B`
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

const renderSnapshotValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return "â€”"
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2)
  }
  return String(value)
}

const isRunActive = (status: PackRunStatus | undefined): boolean =>
  status === PackRunStatusEnum.PENDING || status === PackRunStatusEnum.RUNNING

const MAX_RUN_REFRESH_ATTEMPTS = 60

export default function BoardPackRunViewerPage() {
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const runId = params?.id ?? ""

  const [run, setRun] = useState<RunResponse | null>(null)
  const [sections, setSections] = useState<SectionResponse[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactResponse[]>([])
  const [definitionsById, setDefinitionsById] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<"pdf" | "excel" | null>(null)
  const { scaleLabel } = useFormattedAmount()

  const loadRunBundle = useCallback(
    async (isRefresh = false) => {
      if (!runId) {
        return
      }
      if (isRefresh) {
        setRefreshing(true)
      } else {
        setLoading(true)
      }
      setError(null)
      try {
        const [runResponse, sectionResponse, artifactResponse] = await Promise.all([
          fetchRun(runId),
          fetchSections(runId),
          fetchArtifacts(runId),
        ])
        setRun(runResponse)
        setSections(sectionResponse)
        setArtifacts(artifactResponse)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Failed to load board pack run.")
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [runId],
  )

  useEffect(() => {
    void loadRunBundle()
  }, [loadRunBundle])

  useEffect(() => {
    if (!run || definitionsById[run.definition_id]) {
      return
    }
    let cancelled = false
    const loadDefinitionNames = async () => {
      try {
        const definitions = await fetchDefinitions(false)
        if (cancelled) {
          return
        }
        const map: Record<string, string> = {}
        for (const definition of definitions) {
          map[definition.id] = definition.name
        }
        setDefinitionsById((previous) => ({ ...previous, ...map }))
      } catch {
        // Keep empty name fallback.
      }
    }
    void loadDefinitionNames()
    return () => {
      cancelled = true
    }
  }, [definitionsById, run])

  useEffect(() => {
    if (!isRunActive(run?.status)) {
      return
    }
    let attempts = 0
    const intervalId = window.setInterval(() => {
      if (attempts >= MAX_RUN_REFRESH_ATTEMPTS) {
        setError((previous) => previous ?? "Auto-refresh stopped after reaching the control-plane polling limit. Refresh manually to continue.")
        window.clearInterval(intervalId)
        return
      }
      attempts += 1
      void loadRunBundle(true)
    }, 3000)
    return () => {
      window.clearInterval(intervalId)
    }
  }, [loadRunBundle, run?.status])

  const canDownload = run?.status === PackRunStatusEnum.COMPLETE
  const definitionName = run ? definitionsById[run.definition_id] : null

  const sortedSections = useMemo(
    () => [...sections].sort((left, right) => left.section_order - right.section_order),
    [sections],
  )

  const sortedArtifacts = useMemo(
    () =>
      [...artifacts].sort((left, right) =>
        new Date(right.generated_at).getTime() - new Date(left.generated_at).getTime(),
      ),
    [artifacts],
  )

  const handleDownload = async (format: "pdf" | "excel") => {
    if (!run || !canDownload) {
      return
    }
    setDownloading(format)
    try {
      const blob = await downloadArtifact(run.id, format)
      const objectUrl = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = objectUrl
      link.download = `board_pack_${run.period_start}_${run.period_end}.${format === "pdf" ? "pdf" : "xlsx"}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(objectUrl)
    } catch {
      setError(`Failed to download ${format.toUpperCase()} artifact.`)
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <Button type="button" variant="outline" onClick={() => router.push("/board-pack")}>
          Back
        </Button>
        {refreshing ? (
          <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Refreshing...
          </div>
        ) : null}
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="h-44 animate-pulse rounded-lg border border-border bg-card" />
      ) : null}

      {run ? (
        <>
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-foreground">
                  {definitionName ?? "Board Pack Run"}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {run.period_start} to {run.period_end}
                </p>
                <p className="text-xs italic text-muted-foreground">
                  All amounts are {scaleLabel}
                </p>
                <p className="font-mono text-xs text-muted-foreground">
                  Chain: {run.chain_hash ?? "â€”"}
                </p>
              </div>
              <span
                className={cn(
                  "inline-flex rounded-full px-2 py-1 text-xs font-medium",
                  statusClassMap[run.status],
                  run.status === PackRunStatusEnum.RUNNING ? "animate-pulse" : "",
                )}
              >
                {run.status}
              </span>
            </div>

            {isRunActive(run.status) ? (
              <div className="mt-4 inline-flex items-center gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Generation in progress. Auto-refresh every 3 seconds.
              </div>
            ) : null}

            {run.status === PackRunStatusEnum.FAILED ? (
              <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {run.error_message ?? "Run failed without an explicit error message."}
              </div>
            ) : null}

            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!canDownload || downloading !== null}
                onClick={() => {
                  void handleDownload("pdf")
                }}
              >
                {downloading === "pdf" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Download PDF
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!canDownload || downloading !== null}
                onClick={() => {
                  void handleDownload("excel")
                }}
              >
                {downloading === "excel" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Download Excel
              </Button>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Sections</h2>
            {!sortedSections.length ? (
              <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                No sections available for this run.
              </p>
            ) : null}

            <div className="space-y-2">
              {sortedSections.map((section) => {
                const snapshot = section.data_snapshot ?? null
                const snapshotEntries = snapshot ? Object.entries(snapshot) : []
                return (
                  <details
                    key={section.id}
                    className="rounded-md border border-border bg-background/30"
                  >
                    <summary className="cursor-pointer list-none px-3 py-2 text-sm text-foreground">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span>
                          {section.section_order}. {section.title}
                        </span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {truncate(section.section_hash, 8)}
                        </span>
                      </div>
                    </summary>
                    <div className="border-t border-border px-3 py-3">
                      {snapshotEntries.length ? (
                        <div className="overflow-x-auto rounded-md border border-border">
                          <table className="w-full min-w-[620px] text-sm">
                            <thead>
                              <tr className="bg-muted/30">
                                <th className="px-3 py-2 text-left font-medium text-foreground">
                                  Field
                                </th>
                                <th className="px-3 py-2 text-left font-medium text-foreground">
                                  Value
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {snapshotEntries.map(([key, value]) => (
                                <tr key={`${section.id}-${key}`} className="border-t border-border">
                                  <td className="px-3 py-2 text-muted-foreground">{key}</td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {typeof value === "object" && value !== null ? (
                                      <pre className="whitespace-pre-wrap break-all rounded bg-muted/20 p-2 text-xs text-foreground">
                                        {renderSnapshotValue(value)}
                                      </pre>
                                    ) : (
                                      renderSnapshotValue(value)
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Section data snapshot is not present in this API response.
                        </p>
                      )}
                    </div>
                  </details>
                )
              })}
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-lg font-semibold text-foreground">Artifacts</h2>
            {!sortedArtifacts.length ? (
              <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                No artifacts available.
              </p>
            ) : null}
            <div className="space-y-2">
              {sortedArtifacts.map((artifact) => (
                <div
                  key={artifact.id}
                  className="rounded-md border border-border bg-background/30 px-3 py-2"
                >
                  <p className="text-sm font-medium text-foreground">{artifact.format}</p>
                  <div className="mt-1 grid gap-1 text-xs text-muted-foreground sm:grid-cols-3">
                    <p>Size: {formatBytes(artifact.file_size_bytes)}</p>
                    <p>Generated: {new Date(artifact.generated_at).toLocaleString()}</p>
                    <p className="font-mono">Checksum: {truncate(artifact.checksum, 12)}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}


