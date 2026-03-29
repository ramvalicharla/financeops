"use client"

import { useMemo, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import {
  classifyMultiEntityTrialBalance,
  classifyTrialBalance,
  exportTrialBalance,
  pullRawTrialBalance,
  type GlobalTBResponse,
  type RawTBLineInput,
} from "@/lib/api/coa"
import { useTenantStore } from "@/lib/store/tenant"
import { useDisplayScale } from "@/lib/store/displayScale"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { ScaleSelector } from "@/components/ui/ScaleSelector"
import { Button } from "@/components/ui/button"

const toPeriod = (
  periodStart: string,
  periodEnd: string,
): {
  periodYear?: number
  periodMonth?: number
} => {
  const source = periodEnd || periodStart
  if (!source) {
    return {}
  }
  const parsed = new Date(source)
  if (Number.isNaN(parsed.getTime())) {
    return {}
  }
  return {
    periodYear: parsed.getUTCFullYear(),
    periodMonth: parsed.getUTCMonth() + 1,
  }
}

export default function TrialBalancePage() {
  const { fmt, scale } = useFormattedAmount()
  const setScale = useDisplayScale((state) => state.setScale)
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entityRoles = useTenantStore((state) => state.entity_roles)

  const [periodStart, setPeriodStart] = useState("")
  const [periodEnd, setPeriodEnd] = useState("")
  const [gaap, setGaap] = useState("INDAS")
  const [scope, setScope] = useState<"single" | "all">("single")
  const [viewMode, setViewMode] = useState<"by_entity" | "consolidated">("by_entity")
  const [result, setResult] = useState<GlobalTBResponse | null>(null)
  const [lastRawByEntity, setLastRawByEntity] = useState<Record<string, RawTBLineInput[]>>({})

  const classifyMutation = useMutation({
    mutationFn: async () => {
      if (scope === "single") {
        if (!activeEntityId) {
          throw new Error("Select an entity before classifying.")
        }
        const selectedEntity = entityRoles.find((role) => role.entity_id === activeEntityId)
        if (!selectedEntity) {
          throw new Error("Active entity not found.")
        }
        const period = toPeriod(periodStart, periodEnd)
        const rawTb = await pullRawTrialBalance({
          entity_name: selectedEntity.entity_name,
          period_year: period.periodYear,
          period_month: period.periodMonth,
          period_start: periodStart || undefined,
          period_end: periodEnd || undefined,
        })
        setLastRawByEntity({ [activeEntityId]: rawTb })
        return classifyTrialBalance({
          entity_id: activeEntityId,
          raw_tb: rawTb,
          gaap,
        })
      }

      const payload: Record<string, RawTBLineInput[]> = {}
      const period = toPeriod(periodStart, periodEnd)
      for (const role of entityRoles) {
        payload[role.entity_id] = await pullRawTrialBalance({
          entity_name: role.entity_name,
          period_year: period.periodYear,
          period_month: period.periodMonth,
          period_start: periodStart || undefined,
          period_end: periodEnd || undefined,
        })
      }
      setLastRawByEntity(payload)
      return classifyMultiEntityTrialBalance({
        gaap,
        entity_raw_tbs: payload,
      })
    },
    onSuccess: (data) => setResult(data),
  })

  const exportMutation = useMutation({
    mutationFn: async (format: "csv" | "xlsx") => {
      if (!activeEntityId) {
        throw new Error("Select an entity before export.")
      }
      const rawTb = lastRawByEntity[activeEntityId] ?? []
      return exportTrialBalance({
        entity_id: activeEntityId,
        gaap,
        format,
        raw_tb: rawTb,
      })
    },
    onSuccess: (blob, format) => {
      const extension = format === "csv" ? "csv" : "xlsx"
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `classified_trial_balance.${extension}`
      anchor.click()
      URL.revokeObjectURL(url)
    },
  })

  const renderedLines = useMemo(() => {
    if (!result) {
      return []
    }
    if (viewMode === "consolidated") {
      return result.consolidated
    }
    if (scope === "single" && activeEntityId) {
      return result.entity_results[activeEntityId] ?? []
    }
    return Object.values(result.entity_results).flat()
  }, [activeEntityId, result, scope, viewMode])

  const unmappedNetTotal = useMemo(() => {
    if (!result) {
      return 0
    }
    return result.unmapped_lines.reduce((acc, line) => acc + Number(line.net_amount), 0)
  }, [result])

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Global Trial Balance</h1>
          <p className="text-sm text-muted-foreground">
            Pull trial balance lines, classify via CoA crosswalk, and review unmapped balances.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <ScaleSelector value={scale} onChange={setScale} showGroups />
          <Button
            variant="outline"
            onClick={() => exportMutation.mutate("csv")}
            disabled={!result || exportMutation.isPending}
          >
            Export CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => exportMutation.mutate("xlsx")}
            disabled={!result || exportMutation.isPending}
          >
            Export XLSX
          </Button>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Period start</span>
            <input
              type="date"
              value={periodStart}
              onChange={(event) => setPeriodStart(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Period end</span>
            <input
              type="date"
              value={periodEnd}
              onChange={(event) => setPeriodEnd(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">GAAP</span>
            <select
              value={gaap}
              onChange={(event) => setGaap(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            >
              <option value="INDAS">IndAS</option>
              <option value="IFRS">IFRS</option>
              <option value="MANAGEMENT">Management</option>
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Entity scope</span>
            <select
              value={scope}
              onChange={(event) => setScope(event.target.value as "single" | "all")}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            >
              <option value="single">Selected entity</option>
              <option value="all">All entities</option>
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Entity</span>
            <select
              value={activeEntityId ?? ""}
              onChange={(event) => useTenantStore.getState().setActiveEntity(event.target.value || null)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            >
              <option value="">Select entity</option>
              {entityRoles.map((role) => (
                <option key={role.entity_id} value={role.entity_id}>
                  {role.entity_name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">View mode</span>
            <select
              value={viewMode}
              onChange={(event) => setViewMode(event.target.value as "by_entity" | "consolidated")}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
            >
              <option value="by_entity">By entity</option>
              <option value="consolidated">Consolidated</option>
            </select>
          </label>
        </div>
        <div className="mt-4 flex gap-2">
          <Button onClick={() => classifyMutation.mutate()} disabled={classifyMutation.isPending}>
            Pull + Classify
          </Button>
        </div>
      </section>

      {result ? (
        <section className="flex flex-wrap items-center justify-between rounded-xl border border-border bg-card p-4">
          <div className="text-sm">
            <p className="text-muted-foreground">Balance check</p>
            <p
              className={`font-medium ${
                result.is_balanced ? "text-emerald-300" : "text-rose-300"
              }`}
            >
              {result.is_balanced ? "Balanced" : "Not balanced"}
            </p>
          </div>
          <div className="text-sm">
            <p className="text-muted-foreground">Total debits</p>
            <p className="font-medium text-foreground">{fmt(result.total_debits)}</p>
          </div>
          <div className="text-sm">
            <p className="text-muted-foreground">Total credits</p>
            <p className="font-medium text-foreground">{fmt(result.total_credits)}</p>
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {classifyMutation.isPending ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : classifyMutation.error ? (
          <div className="p-4 text-sm text-[hsl(var(--brand-danger))]">
            Failed to classify trial balance.
          </div>
        ) : renderedLines.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">
            No classified lines available. Select parameters and run classification.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">FS Path</th>
                  <th className="px-4 py-2">Account</th>
                  <th className="px-4 py-2">Debit</th>
                  <th className="px-4 py-2">Credit</th>
                  <th className="px-4 py-2">Net</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {renderedLines.map((line) => (
                  <tr key={`${line.erp_account_code}-${line.platform_account_code}-${line.currency}`}>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {[line.fs_classification, line.fs_schedule, line.fs_line_item, line.fs_subline]
                        .filter(Boolean)
                        .join(" / ") || "Unclassified"}
                    </td>
                    <td className="px-4 py-2">
                      <p className="font-medium text-foreground">
                        {line.platform_account_name ?? line.erp_account_name}
                      </p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {line.platform_account_code ?? line.erp_account_code}
                      </p>
                    </td>
                    <td className="px-4 py-2">{fmt(line.debit_amount)}</td>
                    <td className="px-4 py-2">{fmt(line.credit_amount)}</td>
                    <td className="px-4 py-2">{fmt(line.net_amount)}</td>
                    <td className="px-4 py-2">
                      {line.is_unmapped ? (
                        <span className="rounded-full bg-rose-500/15 px-2 py-1 text-xs text-rose-300">
                          Unmapped
                        </span>
                      ) : line.is_unconfirmed ? (
                        <span className="rounded-full bg-amber-500/15 px-2 py-1 text-xs text-amber-300">
                          Unconfirmed
                        </span>
                      ) : (
                        <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300">
                          Confirmed
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {result && result.unmapped_count > 0 ? (
        <section className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
          <p className="text-sm text-amber-200">
            {result.unmapped_count} accounts ({fmt(unmappedNetTotal.toFixed(2))} total) are
            unmapped and excluded from the classified TB. Go to ERP Mapping to resolve.
          </p>
        </section>
      ) : null}
    </div>
  )
}
