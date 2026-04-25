"use client"

import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { runAccountingRevaluation } from "@/lib/api/fx-rates"
import { useWorkspaceStore } from "@/lib/store/workspace"

const TODAY = new Date().toISOString().slice(0, 10)

export default function AccountingRevaluationPage() {
  const entityId = useWorkspaceStore((s) => s.entityId)
  const [asOfDate, setAsOfDate] = useState(TODAY)
  const [error, setError] = useState<string | null>(null)

  const runMutation = useMutation({
    mutationFn: runAccountingRevaluation,
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Failed to run revaluation")
    },
  })

  const runNow = async () => {
    setError(null)
    if (!entityId) {
      setError("Select an active entity before running revaluation.")
      return
    }
    await runMutation.mutateAsync({
      org_entity_id: entityId,
      as_of_date: asOfDate,
    })
  }

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-2xl font-semibold text-foreground">FX Revaluation</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Revalue foreign-currency monetary balances using closing rates and post the adjustment JV.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">As of date</span>
            <input
              type="date"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
              value={asOfDate}
              onChange={(event) => setAsOfDate(event.target.value)}
            />
          </label>
          <div className="flex items-end">
            <Button
              type="button"
              onClick={() => void runNow()}
              disabled={runMutation.isPending}
            >
              {runMutation.isPending ? "Running..." : "Run Revaluation"}
            </Button>
          </div>
        </div>
      </section>

      {runMutation.data ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-lg font-semibold text-foreground">Latest Run</h2>
          <dl className="mt-3 grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Run ID</dt>
              <dd className="font-mono text-foreground">{runMutation.data.run_id}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Status</dt>
              <dd className="text-foreground">{runMutation.data.status}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Functional Currency</dt>
              <dd className="text-foreground">{runMutation.data.functional_currency}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Line Count</dt>
              <dd className="text-foreground">{runMutation.data.line_count}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Total FX Difference</dt>
              <dd className="text-foreground">{runMutation.data.total_fx_difference}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Adjustment JV</dt>
              <dd className="font-mono text-foreground">{runMutation.data.adjustment_jv_id ?? "-"}</dd>
            </div>
          </dl>
        </section>
      ) : null}

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}

