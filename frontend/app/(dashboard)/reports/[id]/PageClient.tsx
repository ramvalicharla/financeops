"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Download, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  downloadReportResult,
  fetchMetrics,
  fetchReportDefinitions,
  fetchReportResult,
  fetchReportRun,
} from "@/lib/api/report-builder"
import type {
  MetricDefinition,
  ReportDefinitionResponse,
  ReportResultResponse,
  ReportResultRow,
  ReportRunResponse,
  ReportRunStatus,
} from "@/lib/types/report-builder"
import { ReportRunStatus as ReportRunStatusEnum } from "@/lib/types/report-builder"
import { cn } from "@/lib/utils"

const statusClassMap: Record<ReportRunStatus, string> = {
  [ReportRunStatusEnum.PENDING]: "bg-yellow-500/20 text-yellow-300",
  [ReportRunStatusEnum.RUNNING]: "bg-blue-500/20 text-blue-300",
  [ReportRunStatusEnum.COMPLETE]:
    "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]",
  [ReportRunStatusEnum.FAILED]:
    "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]",
}

const humanizeKey = (value: string): string =>
  value
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())

const formatDateTime = (value: string | null): string => {
  if (!value) return "-"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

const valueToString = (value: unknown): string => {
  if (value === null || value === undefined) return "-"
  if (typeof value === "object") return JSON.stringify(value)
  return String(value)
}

const getRows = (result: ReportResultResponse | null): ReportResultRow[] => {
  if (!result) return []
  return Array.isArray(result.result_data)
    ? (result.result_data.filter(
        (entry): entry is ReportResultRow =>
          Boolean(entry) && typeof entry === "object" && !Array.isArray(entry),
      ) as ReportResultRow[])
    : []
}

const isRunActive = (status: ReportRunStatus | undefined): boolean =>
  status === ReportRunStatusEnum.PENDING || status === ReportRunStatusEnum.RUNNING

const MAX_RUN_REFRESH_ATTEMPTS = 60

export default function ReportRunViewerPage() {
  const router = useRouter()
  const params = useParams<{ id: string }>()
  const runId = params?.id ?? ""

  const [run, setRun] = useState<ReportRunResponse | null>(null)
  const [definitions, setDefinitions] = useState<ReportDefinitionResponse[]>([])
  const [metrics, setMetrics] = useState<MetricDefinition[]>([])
  const [result, setResult] = useState<ReportResultResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<"csv" | "excel" | "pdf" | null>(null)
  const [pageIndex, setPageIndex] = useState(0)

  const loadBundle = useCallback(
    async (isRefresh = false) => {
      if (!runId) return
      if (isRefresh) setRefreshing(true)
      else setLoading(true)
      setError(null)
      try {
        const [runResponse, definitionResponse, metricResponse] = await Promise.all([
          fetchReportRun(runId),
          fetchReportDefinitions(false),
          fetchMetrics(),
        ])
        setRun(runResponse)
        setDefinitions(definitionResponse)
        setMetrics(metricResponse)
        if (runResponse.status === ReportRunStatusEnum.COMPLETE) {
          setResult(await fetchReportResult(runId))
        } else {
          setResult(null)
        }
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Failed to load report run.")
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [runId],
  )

  useEffect(() => {
    void loadBundle()
  }, [loadBundle])

  useEffect(() => {
    if (!isRunActive(run?.status)) return
    let attempts = 0
    const intervalId = window.setInterval(() => {
      if (attempts >= MAX_RUN_REFRESH_ATTEMPTS) {
        setError((previous) => previous ?? "Auto-refresh stopped after reaching the control-plane polling limit. Refresh manually to continue.")
        window.clearInterval(intervalId)
        return
      }
      attempts += 1
      void loadBundle(true)
    }, 3000)
    return () => window.clearInterval(intervalId)
  }, [loadBundle, run?.status])

  const definition = useMemo(
    () => definitions.find((item) => item.id === run?.definition_id) ?? null,
    [definitions, run?.definition_id],
  )
  const metricByKey = useMemo(() => {
    const map = new Map<string, MetricDefinition>()
    for (const metric of metrics) map.set(metric.key, metric)
    return map
  }, [metrics])
  const rows = useMemo(() => getRows(result), [result])
  const columns = useMemo(() => (rows.length ? Object.keys(rows[0]) : []), [rows])
  const pageSize = 25
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const paginatedRows = useMemo(
    () => rows.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize),
    [pageIndex, rows],
  )

  useEffect(() => {
    setPageIndex(0)
  }, [result?.id])

  const formats = useMemo(() => {
    if (!definition) return []
    return definition.export_formats.map((format) => format.toLowerCase())
  }, [definition])

  const download = async (format: "csv" | "excel" | "pdf") => {
    if (!run || run.status !== ReportRunStatusEnum.COMPLETE) return
    setDownloading(format)
    try {
      const blob = await downloadReportResult(run.id, format)
      const objectUrl = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = objectUrl
      link.download = `custom_report_${run.id}.${format === "excel" ? "xlsx" : format}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(objectUrl)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Download failed.")
    } finally {
      setDownloading(null)
    }
  }

  const complete = run?.status === ReportRunStatusEnum.COMPLETE

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-2">
        <Button type="button" variant="outline" onClick={() => router.push("/reports")}>
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

      {loading ? <div className="h-40 animate-pulse rounded-lg border border-border bg-card" /> : null}

      {run ? (
        <>
          <section className="rounded-lg border border-border bg-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <h1 className="text-xl font-semibold text-foreground">
                  {definition?.name ?? "Custom Report Run"}
                </h1>
                <p className="text-sm text-muted-foreground">
                  Rows: {run.row_count ?? "-"} | Started: {formatDateTime(run.started_at)} |
                  Completed: {formatDateTime(run.completed_at)}
                </p>
              </div>
              <span className={cn("inline-flex rounded-full px-2 py-1 text-xs font-medium", statusClassMap[run.status], run.status === ReportRunStatusEnum.RUNNING ? "animate-pulse" : "")}>
                {run.status}
              </span>
            </div>

            {isRunActive(run.status) ? (
              <div className="mt-4 inline-flex items-center gap-2 rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Report is in progress. Auto-refresh every 3 seconds.
              </div>
            ) : null}

            {run.status === ReportRunStatusEnum.FAILED ? (
              <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {run.error_message ?? "Report run failed."}
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-border bg-card p-4">
            <h2 className="mb-3 text-base font-semibold text-foreground">Downloads</h2>
            <div className="flex flex-wrap gap-2">
              {(["csv", "excel", "pdf"] as const).map((format) =>
                formats.includes(format) ? (
                  <Button key={format} type="button" variant="outline" disabled={!complete || downloading !== null} onClick={() => { void download(format) }}>
                    {downloading === format ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                    Download {format.toUpperCase()}
                  </Button>
                ) : null,
              )}
            </div>
          </section>

          {complete ? (
            <section className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-base font-semibold text-foreground">Result</h2>
              {!rows.length ? (
                <p className="rounded-md border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                  No result rows available.
                </p>
              ) : (
                <>
                  <div className="overflow-x-auto rounded-md border border-border">
                    <table aria-label="Report runs" className="w-full min-w-[780px] text-sm">
                      <thead>
                        <tr className="bg-muted/30">
                          {columns.map((column) => (
                            <th
                              key={column}
                              scope="col"
                              className="px-3 py-2 text-left font-medium text-foreground"
                            >
                              {metricByKey.get(column)?.label ?? humanizeKey(column)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedRows.map((row, rowIndex) => (
                          <tr key={`${pageIndex}-${rowIndex}`} className="border-t border-border">
                            {columns.map((column) => (
                              <td key={`${rowIndex}-${column}`} className="px-3 py-2 text-muted-foreground">
                                {valueToString(row[column])}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-sm">
                    <p className="text-muted-foreground">Page {pageIndex + 1} of {totalPages}</p>
                    <div className="flex gap-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => setPageIndex((value) => Math.max(value - 1, 0))} disabled={pageIndex === 0}>Prev</Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => setPageIndex((value) => Math.min(value + 1, totalPages - 1))} disabled={pageIndex >= totalPages - 1}>Next</Button>
                    </div>
                  </div>
                </>
              )}
              {result ? (
                <p className="mt-4 font-mono text-xs text-muted-foreground">
                  Result hash: {result.result_hash}
                </p>
              ) : null}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
