"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import { ScenarioComparison } from "@/components/scenarios/ScenarioComparison"
import { ScenarioSlider } from "@/components/scenarios/ScenarioSlider"
import { WaterfallChart } from "@/components/scenarios/WaterfallChart"
import {
  computeScenarios,
  exportScenarioSet,
  getScenarioComparison,
  getScenarioSet,
  updateScenarioDefinition,
} from "@/lib/api/scenarios"
import type { ScenarioComparisonPayload, ScenarioDefinition } from "@/lib/types/scenario"
import { decimalStringToNumber } from "@/lib/utils"

export default function ScenarioDetailPage() {
  const params = useParams()
  const setId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""
  const [definitions, setDefinitions] = useState<ScenarioDefinition[]>([])
  const [comparison, setComparison] = useState<ScenarioComparisonPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const detail = await getScenarioSet(setId)
      setDefinitions(detail.scenario_definitions)
      const computed = await computeScenarios(setId)
      if (computed.results.length > 0) {
        setComparison(await getScenarioComparison(setId))
      } else {
        setComparison(null)
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load scenario set")
    } finally {
      setLoading(false)
    }
  }, [setId])

  useEffect(() => {
    if (setId) void load()
  }, [setId, load])

  const optimisticDefinition = useMemo(
    () => definitions.find((row) => row.scenario_name === "optimistic") ?? definitions[0],
    [definitions],
  )

  const sliderValues = useMemo(() => {
    const overrides = optimisticDefinition?.driver_overrides ?? {}
    return {
      revenue_growth_pct_monthly: Number.parseFloat(overrides.revenue_growth_pct_monthly ?? "8.00"),
      cogs_pct_of_revenue: Number.parseFloat(overrides.cogs_pct_of_revenue ?? "55.00"),
      opex_growth_pct_monthly: Number.parseFloat(overrides.opex_growth_pct_monthly ?? "3.00"),
    }
  }, [optimisticDefinition])

  const impactPreview = useMemo(() => {
    if (!comparison) return "0.0%"
    const base = comparison.scenarios.find((row) => row.is_base_case)
    const optimistic = comparison.scenarios.find((row) => row.scenario_name === "optimistic")
    if (!base || !optimistic) return "0.0%"
    const baseValue = decimalStringToNumber(base.summary.ebitda_total)
    const optValue = decimalStringToNumber(optimistic.summary.ebitda_total)
    if (baseValue === 0) return "0.0%"
    const pct = ((optValue - baseValue) / baseValue) * 100
    return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`
  }, [comparison])

  const handleSaveOverrides = async (values: Record<string, string>) => {
    if (!optimisticDefinition) return
    await updateScenarioDefinition(setId, optimisticDefinition.id, {
      driver_overrides: values,
    })
  }

  const handleRecompute = async () => {
    await computeScenarios(setId)
    setComparison(await getScenarioComparison(setId))
  }

  const handleExport = async () => {
    const blob = await exportScenarioSet(setId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `scenarios_${setId}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Scenario Comparison</h1>
          <p className="text-sm text-muted-foreground">Compare base, optimistic, and pessimistic projections.</p>
        </div>
        <button
          type="button"
          onClick={handleExport}
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Export
        </button>
      </header>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      {comparison ? (
        <>
          <ScenarioComparison scenarios={comparison.scenarios} />
          <WaterfallChart waterfall={comparison.waterfall} />
          <ScenarioSlider
            values={sliderValues}
            onChange={handleSaveOverrides}
            onRecompute={handleRecompute}
            impactPreview={impactPreview}
          />
        </>
      ) : null}
    </div>
  )
}
