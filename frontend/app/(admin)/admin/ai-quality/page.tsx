"use client"

import { useEffect, useMemo, useState } from "react"
import {
  listLearningBenchmarkResults,
  listRecentLearningSignals,
  runLearningBenchmarks,
} from "@/lib/api/learning"
import type { BenchmarkResult, LearningSignalSummary } from "@/lib/types/learning"
import { BenchmarkChart } from "@/components/admin/BenchmarkChart"
import { LearningSignalTable } from "@/components/admin/LearningSignalTable"

export default function AIQualityPage() {
  const [results, setResults] = useState<BenchmarkResult[]>([])
  const [signals, setSignals] = useState<LearningSignalSummary[]>([])
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    const benchmarkPayload = await listLearningBenchmarkResults({ limit: 100, offset: 0 })
    setResults(benchmarkPayload.data)

    try {
      const recentSignals = await listRecentLearningSignals({ limit: 30 })
      setSignals(recentSignals)
    } catch {
      setSignals([])
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const summary = useMemo(() => {
    if (results.length === 0) {
      return {
        latestAccuracy: null as string | null,
        runs: 0,
      }
    }
    const latest = [...results].sort((a, b) => b.run_at.localeCompare(a.run_at))[0]
    return {
      latestAccuracy: `${(Number.parseFloat(latest.accuracy_pct || "0") * 100).toFixed(2)}%`,
      runs: results.length,
    }
  }, [results])

  const onRunBenchmarks = async () => {
    setRunning(true)
    setMessage(null)
    try {
      const payload = await runLearningBenchmarks()
      setMessage(`Benchmarks completed (${payload.results.length} suites).`)
      await load()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to run benchmarks")
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">AI Quality</h1>
          <p className="text-sm text-muted-foreground">
            Benchmark accuracy trend and recent learning signals across tenants.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void onRunBenchmarks()}
          disabled={running}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          {running ? "Running..." : "Run Benchmarks"}
        </button>
      </header>

      <section className="grid gap-3 md:grid-cols-3">
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Latest Accuracy</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">
            {summary.latestAccuracy ?? "N/A"}
          </p>
        </article>
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Benchmark Runs</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summary.runs}</p>
        </article>
        <article className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Recent Signals</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">{signals.length}</p>
        </article>
      </section>

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

      <BenchmarkChart results={results} />

      <section className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Recent Learning Signals</h2>
        <LearningSignalTable signals={signals} />
      </section>
    </div>
  )
}

