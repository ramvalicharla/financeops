"use client"

import { useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { Button } from "@/components/ui/button"
import { ConsolidationSummary } from "@/components/consolidation/ConsolidationSummary"
import { EntitySelector } from "@/components/consolidation/EntitySelector"
import {
  useConsolidationEntities,
  useConsolidationSummary,
  useFXRates,
} from "@/hooks/useConsolidation"

const currentMonth = new Date().toISOString().slice(0, 7)

export default function ConsolidationPage() {
  const { data: session } = useSession()
  const tenantId = session?.user?.tenant_id
  const [period, setPeriod] = useState(currentMonth)
  const entitiesQuery = useConsolidationEntities(tenantId)
  const fxRatesQuery = useFXRates(period)
  const [selectedEntityIds, setSelectedEntityIds] = useState<string[]>([])

  useEffect(() => {
    if (!entitiesQuery.data?.length || selectedEntityIds.length > 0) {
      return
    }
    setSelectedEntityIds(
      entitiesQuery.data
        .filter((entity) => entity.is_included)
        .map((entity) => entity.entity_id),
    )
  }, [entitiesQuery.data, selectedEntityIds.length])

  const mergedEntities = useMemo(() => {
    const rates = new Map(
      (fxRatesQuery.data ?? []).map((rate) => [rate.currency, rate.rate_to_inr]),
    )
    return (entitiesQuery.data ?? []).map((entity) => ({
      ...entity,
      fx_rate_to_inr: rates.get(entity.currency) ?? entity.fx_rate_to_inr,
    }))
  }, [entitiesQuery.data, fxRatesQuery.data])

  const summaryQuery = useConsolidationSummary(selectedEntityIds, period)

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="consolidation-period">
              Period
            </label>
            <input
              id="consolidation-period"
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              type="month"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
            />
          </div>
          <Button
            type="button"
            disabled={!selectedEntityIds.length || summaryQuery.isFetching}
            onClick={() => {
              void summaryQuery.refetch()
            }}
          >
            {summaryQuery.isFetching ? "Running..." : "Run Consolidation"}
          </Button>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        {entitiesQuery.isError ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            Failed to load consolidation entities.
          </p>
        ) : null}
        <EntitySelector
          entities={mergedEntities}
          selectedEntityIds={selectedEntityIds}
          onSelectionChange={setSelectedEntityIds}
        />
        <ConsolidationSummary
          summary={summaryQuery.data ?? null}
          isLoading={summaryQuery.isFetching}
        />
      </div>
      {summaryQuery.isError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to run consolidation summary.
        </p>
      ) : null}
    </div>
  )
}
