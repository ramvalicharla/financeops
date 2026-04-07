"use client"

import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import {
  getConsolidationTranslation,
  getOrgSetupSummaryForConsolidation,
} from "@/lib/api/consolidation"

const TODAY = new Date().toISOString().slice(0, 10)

export default function ConsolidationTranslationPage() {
  const [asOfDate, setAsOfDate] = useState(TODAY)
  const [presentationCurrency, setPresentationCurrency] = useState("INR")
  const [error, setError] = useState<string | null>(null)

  const orgSetupQuery = useQuery({
    queryKey: ["org-setup-summary-consolidation-translation"],
    queryFn: getOrgSetupSummaryForConsolidation,
  })
  const orgGroupId = orgSetupQuery.data?.group?.id ?? ""

  const runMutation = useMutation({
    mutationFn: getConsolidationTranslation,
    onError: (cause) => {
      setError(cause instanceof Error ? cause.message : "Failed to run translation")
    },
  })

  const runTranslation = async () => {
    setError(null)
    if (!orgGroupId) {
      setError("Organisation group is not configured.")
      return
    }
    await runMutation.mutateAsync({
      orgGroupId,
      presentationCurrency: presentationCurrency.toUpperCase(),
      asOfDate,
    })
  }

  return (
    <div className="space-y-6 p-6">
      <section className="rounded-xl border border-border bg-card p-4">
        <h1 className="text-2xl font-semibold text-foreground">Consolidation Translation</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Translate entity financials to presentation currency, compute CTA, and persist run history.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">As of date</span>
            <input
              type="date"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
              value={asOfDate}
              onChange={(event) => setAsOfDate(event.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Presentation currency</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
              value={presentationCurrency}
              onChange={(event) => setPresentationCurrency(event.target.value)}
              placeholder="INR"
            />
          </label>
          <div className="flex items-end">
            <Button
              type="button"
              disabled={runMutation.isPending}
              onClick={() => void runTranslation()}
            >
              {runMutation.isPending ? "Running..." : "Run Translation"}
            </Button>
          </div>
        </div>
      </section>

      {runMutation.data ? (
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-lg font-semibold text-foreground">Translation Result</h2>
            <p className="text-sm text-muted-foreground">
              CTA account: {runMutation.data.cta_account_code}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table aria-label="Currency translation" className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th scope="col" className="px-4 py-2">Entity</th>
                  <th scope="col" className="px-4 py-2">Closing</th>
                  <th scope="col" className="px-4 py-2">Average</th>
                  <th scope="col" className="px-4 py-2 text-right">Assets</th>
                  <th scope="col" className="px-4 py-2 text-right">Liabilities</th>
                  <th scope="col" className="px-4 py-2 text-right">Equity</th>
                  <th scope="col" className="px-4 py-2 text-right">Net Profit</th>
                  <th scope="col" className="px-4 py-2 text-right">CTA</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {runMutation.data.entity_results.map((row) => (
                  <tr key={row.org_entity_id}>
                    <td className="px-4 py-2">{row.entity_name}</td>
                    <td className="px-4 py-2">{row.closing_rate}</td>
                    <td className="px-4 py-2">{row.average_rate}</td>
                    <td className="px-4 py-2 text-right">{row.translated_assets}</td>
                    <td className="px-4 py-2 text-right">{row.translated_liabilities}</td>
                    <td className="px-4 py-2 text-right">{row.translated_equity}</td>
                    <td className="px-4 py-2 text-right">{row.translated_net_profit}</td>
                    <td className="px-4 py-2 text-right">{row.cta_amount}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-muted/20">
                <tr className="text-sm font-semibold text-foreground">
                  <td className="px-4 py-2" colSpan={3}>Totals</td>
                  <td className="px-4 py-2 text-right">{runMutation.data.totals.translated_assets}</td>
                  <td className="px-4 py-2 text-right">{runMutation.data.totals.translated_liabilities}</td>
                  <td className="px-4 py-2 text-right">{runMutation.data.totals.translated_equity}</td>
                  <td className="px-4 py-2 text-right">{runMutation.data.totals.translated_net_profit}</td>
                  <td className="px-4 py-2 text-right">{runMutation.data.totals.total_cta}</td>
                </tr>
              </tfoot>
            </table>
          </div>
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
