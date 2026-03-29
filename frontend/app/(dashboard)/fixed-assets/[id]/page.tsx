"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  disposeAsset,
  getAsset,
  listDepreciationHistory,
  listImpairmentHistory,
  listRevaluationHistory,
  postImpairment,
  postRevaluation,
  runAssetDepreciation,
} from "@/lib/api/fixedAssets"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface FixedAssetDetailPageProps {
  params: {
    id: string
  }
}

export default function FixedAssetDetailPage({ params }: FixedAssetDetailPageProps) {
  const queryClient = useQueryClient()
  const { fmt } = useFormattedAmount()

  const [gaap, setGaap] = useState("INDAS")
  const [depStart, setDepStart] = useState("")
  const [depEnd, setDepEnd] = useState("")

  const [revaluationDate, setRevaluationDate] = useState("")
  const [revaluationMethod, setRevaluationMethod] = useState("PROPORTIONAL")
  const [fairValue, setFairValue] = useState("")

  const [impairmentDate, setImpairmentDate] = useState("")
  const [valueInUse, setValueInUse] = useState("")
  const [fvlcts, setFvlcts] = useState("")
  const [discountRate, setDiscountRate] = useState("")

  const [disposalDate, setDisposalDate] = useState("")
  const [disposalProceeds, setDisposalProceeds] = useState("")

  const assetQuery = useQuery({
    queryKey: ["fa-asset", params.id],
    queryFn: () => getAsset(params.id),
  })

  const depreciationQuery = useQuery({
    queryKey: ["fa-dep-history", params.id],
    queryFn: () => listDepreciationHistory(params.id, 0, 50),
  })

  const revaluationQuery = useQuery({
    queryKey: ["fa-revaluation-history", params.id],
    queryFn: () => listRevaluationHistory(params.id),
  })

  const impairmentQuery = useQuery({
    queryKey: ["fa-impairment-history", params.id],
    queryFn: () => listImpairmentHistory(params.id),
  })

  const depMutation = useMutation({
    mutationFn: () => runAssetDepreciation(params.id, { period_start: depStart, period_end: depEnd, gaap }),
    onSuccess: () => {
      setDepStart("")
      setDepEnd("")
      void queryClient.invalidateQueries({ queryKey: ["fa-dep-history", params.id] })
      void queryClient.invalidateQueries({ queryKey: ["fa-asset", params.id] })
    },
  })

  const revaluationMutation = useMutation({
    mutationFn: () =>
      postRevaluation(params.id, {
        fair_value: fairValue,
        method: revaluationMethod as "PROPORTIONAL" | "ELIMINATION",
        revaluation_date: revaluationDate,
      }),
    onSuccess: () => {
      setFairValue("")
      setRevaluationDate("")
      void queryClient.invalidateQueries({ queryKey: ["fa-revaluation-history", params.id] })
      void queryClient.invalidateQueries({ queryKey: ["fa-asset", params.id] })
    },
  })

  const impairmentMutation = useMutation({
    mutationFn: () =>
      postImpairment(params.id, {
        impairment_date: impairmentDate,
        value_in_use: valueInUse || undefined,
        fvlcts: fvlcts || undefined,
        discount_rate: discountRate || undefined,
      }),
    onSuccess: () => {
      setImpairmentDate("")
      setValueInUse("")
      setFvlcts("")
      setDiscountRate("")
      void queryClient.invalidateQueries({ queryKey: ["fa-impairment-history", params.id] })
      void queryClient.invalidateQueries({ queryKey: ["fa-asset", params.id] })
    },
  })

  const disposalMutation = useMutation({
    mutationFn: () => disposeAsset(params.id, { disposal_date: disposalDate, proceeds: disposalProceeds }),
    onSuccess: () => {
      setDisposalDate("")
      setDisposalProceeds("")
      void queryClient.invalidateQueries({ queryKey: ["fa-asset", params.id] })
    },
  })

  const latestDep = useMemo(() => depreciationQuery.data?.items.at(0) ?? null, [depreciationQuery.data])

  if (assetQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        {Array.from({ length: 5 }).map((_, idx) => (
          <div key={idx} className="h-12 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    )
  }

  if (assetQuery.error || !assetQuery.data) {
    return <div className="p-6 text-sm text-[hsl(var(--brand-danger))]">Failed to load asset details.</div>
  }

  const asset = assetQuery.data
  const accumulatedDep = latestDep?.accumulated_dep ?? "0"
  const nbv = latestDep?.closing_nbv ?? asset.original_cost

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{asset.asset_name}</h1>
          <p className="font-mono text-xs text-muted-foreground">{asset.asset_code}</p>
        </div>
        <span className="rounded-full bg-accent px-3 py-1 text-xs text-accent-foreground">{asset.status}</span>
      </header>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Cost</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(asset.original_cost)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Accumulated Dep</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(accumulatedDep)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">NBV</p>
          <p className="mt-1 text-xl font-semibold text-foreground">{fmt(nbv)}</p>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-medium text-foreground">Actions</h2>
          <select
            value={gaap}
            onChange={(event) => setGaap(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="INDAS">IndAS</option>
            <option value="IFRS">IFRS</option>
            <option value="IT_ACT">IT Act</option>
          </select>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2 rounded-lg border border-border p-3">
            <h3 className="text-sm font-medium text-foreground">Post Depreciation Run</h3>
            <Input type="date" value={depStart} onChange={(event) => setDepStart(event.target.value)} />
            <Input type="date" value={depEnd} onChange={(event) => setDepEnd(event.target.value)} />
            <Button onClick={() => depMutation.mutate()} disabled={!depStart || !depEnd || depMutation.isPending}>
              Post Run
            </Button>
          </div>

          <div className="space-y-2 rounded-lg border border-border p-3">
            <h3 className="text-sm font-medium text-foreground">Post Revaluation</h3>
            <Input value={fairValue} onChange={(event) => setFairValue(event.target.value)} placeholder="Fair value" />
            <Input
              type="date"
              value={revaluationDate}
              onChange={(event) => setRevaluationDate(event.target.value)}
            />
            <select
              value={revaluationMethod}
              onChange={(event) => setRevaluationMethod(event.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="PROPORTIONAL">Proportional</option>
              <option value="ELIMINATION">Elimination</option>
            </select>
            <Button
              onClick={() => revaluationMutation.mutate()}
              disabled={!fairValue || !revaluationDate || revaluationMutation.isPending}
            >
              Post Revaluation
            </Button>
          </div>

          <div className="space-y-2 rounded-lg border border-border p-3">
            <h3 className="text-sm font-medium text-foreground">Post Impairment</h3>
            <Input
              type="date"
              value={impairmentDate}
              onChange={(event) => setImpairmentDate(event.target.value)}
            />
            <Input value={valueInUse} onChange={(event) => setValueInUse(event.target.value)} placeholder="Value in use" />
            <Input value={fvlcts} onChange={(event) => setFvlcts(event.target.value)} placeholder="FVLCTS" />
            <Input
              value={discountRate}
              onChange={(event) => setDiscountRate(event.target.value)}
              placeholder="Discount rate"
            />
            <Button
              onClick={() => impairmentMutation.mutate()}
              disabled={
                !impairmentDate ||
                (!valueInUse && !fvlcts) ||
                impairmentMutation.isPending
              }
            >
              Post Impairment
            </Button>
          </div>

          <div className="space-y-2 rounded-lg border border-border p-3">
            <h3 className="text-sm font-medium text-foreground">Dispose Asset</h3>
            <Input type="date" value={disposalDate} onChange={(event) => setDisposalDate(event.target.value)} />
            <Input
              value={disposalProceeds}
              onChange={(event) => setDisposalProceeds(event.target.value)}
              placeholder="Disposal proceeds"
            />
            <Button
              variant="outline"
              onClick={() => disposalMutation.mutate()}
              disabled={!disposalDate || !disposalProceeds || disposalMutation.isPending}
            >
              Mark Disposed
            </Button>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-lg font-medium text-foreground">Depreciation History</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted/30">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-2">Period</th>
                <th className="px-4 py-2">GAAP</th>
                <th className="px-4 py-2">Opening NBV</th>
                <th className="px-4 py-2">Depreciation</th>
                <th className="px-4 py-2">Closing NBV</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(depreciationQuery.data?.items ?? []).map((run) => (
                <tr key={run.id}>
                  <td className="px-4 py-2">
                    {run.period_start} to {run.period_end}
                  </td>
                  <td className="px-4 py-2">{run.gaap}</td>
                  <td className="px-4 py-2">{fmt(run.opening_nbv)}</td>
                  <td className="px-4 py-2">{fmt(run.depreciation_amount)}</td>
                  <td className="px-4 py-2">{fmt(run.closing_nbv)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-lg font-medium text-foreground">Revaluation History</h2>
          </div>
          <div className="space-y-2 p-4">
            {(revaluationQuery.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No revaluation records.</p>
            ) : (
              (revaluationQuery.data ?? []).map((row) => (
                <div key={row.id} className="rounded-md border border-border p-3 text-sm">
                  <p className="text-foreground">{row.revaluation_date} - {row.method}</p>
                  <p className="text-muted-foreground">Fair value: {fmt(row.fair_value)}</p>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-lg font-medium text-foreground">Impairment History</h2>
          </div>
          <div className="space-y-2 p-4">
            {(impairmentQuery.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No impairment records.</p>
            ) : (
              (impairmentQuery.data ?? []).map((row) => (
                <div key={row.id} className="rounded-md border border-border p-3 text-sm">
                  <p className="text-foreground">{row.impairment_date}</p>
                  <p className="text-muted-foreground">Loss: {fmt(row.impairment_loss)}</p>
                </div>
              ))
            )}
          </div>
        </article>
      </section>
    </div>
  )
}
