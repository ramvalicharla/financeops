"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { createScenarioSet, getScenarioSet, listScenarioSets } from "@/lib/api/scenarios"
import type { ScenarioSet } from "@/lib/types/scenario"

type ScenarioCard = ScenarioSet & { scenario_names: string[]; last_computed: string | null }

export default function ScenariosPage() {
  const [rows, setRows] = useState<ScenarioCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listScenarioSets({ limit: 100, offset: 0 })
      const cards: ScenarioCard[] = []
      for (const set of payload.data) {
        const detail = await getScenarioSet(set.id)
        cards.push({
          ...set,
          scenario_names: detail.scenario_definitions.map((row) => row.scenario_label),
          last_computed: detail.latest_results[0]?.computed_at ?? null,
        })
      }
      setRows(cards)
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load scenario sets")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const createSet = async () => {
    try {
      await createScenarioSet({
        name: `Planning ${new Date().toISOString().slice(0, 7)}`,
        base_period: new Date().toISOString().slice(0, 7),
        horizon_months: 12,
      })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create scenario set")
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Scenario Modelling</h1>
          <p className="text-sm text-muted-foreground">What-if analysis across base, upside, and downside cases.</p>
        </div>
        <button
          type="button"
          onClick={createSet}
          className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          <Plus className="h-4 w-4" />
          New Scenario Set
        </button>
      </header>

      {loading ? <div className="h-36 animate-pulse rounded-xl bg-muted" /> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((row) => (
          <Link key={row.id} href={`/scenarios/${row.id}`} className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm font-semibold text-foreground">{row.name}</p>
            <p className="text-xs text-muted-foreground">Base period: {row.base_period}</p>
            <p className="mt-2 text-xs text-muted-foreground">{row.scenario_names.join(" · ")}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Last computed: {row.last_computed ? new Date(row.last_computed).toLocaleString() : "Not computed"}
            </p>
          </Link>
        ))}
      </div>
    </div>
  )
}

