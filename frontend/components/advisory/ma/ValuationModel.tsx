"use client"

import { useMemo, useState } from "react"
import type { MAValuation } from "@/lib/types/ma"
import { formatINR } from "@/lib/utils"

interface ValuationModelProps {
  valuations: MAValuation[]
  onCreate: (payload: {
    valuation_name: string
    valuation_method: string
    assumptions: Record<string, string>
  }) => Promise<void>
}

const dcfDefaults: Record<string, string> = {
  ebitda_base: "1000000.00",
  revenue_base: "4000000.00",
  revenue_growth_year_1: "0.05",
  revenue_growth_year_2: "0.05",
  revenue_growth_year_3: "0.05",
  revenue_growth_year_4: "0.05",
  revenue_growth_year_5: "0.05",
  ebitda_margin_year_1: "0.20",
  ebitda_margin_year_2: "0.20",
  ebitda_margin_year_3: "0.20",
  ebitda_margin_year_4: "0.20",
  ebitda_margin_year_5: "0.20",
  terminal_growth_rate: "0.03",
  discount_rate: "0.12",
  tax_rate: "0.25",
  capex_pct_revenue: "0.04",
  nwc_change_pct_revenue: "0.02",
  net_debt: "200.00",
}

const comparableDefaults: Record<string, string> = {
  ltm_ebitda: "100.00",
  ltm_revenue: "500.00",
  peer_ev_ebitda_median: "10.00",
  peer_ev_revenue_median: "2.00",
  control_premium_pct: "0.25",
  net_debt: "0.00",
}

export function ValuationModel({ valuations, onCreate }: ValuationModelProps) {
  const [name, setName] = useState("Base Case")
  const [method, setMethod] = useState("dcf")
  const [assumptions, setAssumptions] = useState<Record<string, string>>(dcfDefaults)
  const [saving, setSaving] = useState(false)

  const assumptionKeys = useMemo(
    () => Object.keys(method === "dcf" ? dcfDefaults : comparableDefaults),
    [method],
  )

  const handleMethodChange = (value: string) => {
    setMethod(value)
    setAssumptions(value === "dcf" ? dcfDefaults : comparableDefaults)
  }

  const submit = async () => {
    setSaving(true)
    try {
      await onCreate({
        valuation_name: name,
        valuation_method: method,
        assumptions,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">New Valuation</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Valuation name"
          />
          <select
            value={method}
            onChange={(event) => handleMethodChange(event.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="dcf">DCF</option>
            <option value="comparable_companies">Comparable Companies</option>
          </select>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {assumptionKeys.map((key) => (
            <label key={key} className="text-xs text-muted-foreground">
              {key}
              <input
                value={assumptions[key] ?? ""}
                onChange={(event) => setAssumptions((prev) => ({ ...prev, [key]: event.target.value }))}
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={saving}
          className="mt-4 rounded-md border border-border px-3 py-2 text-sm text-foreground disabled:opacity-50"
        >
          {saving ? "Computing..." : "Compute Valuation"}
        </button>
      </article>

      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">Valuation History</h3>
        <div className="mt-3 space-y-2">
          {valuations.map((row) => (
            <div key={row.id} className="rounded-md border border-border/60 bg-background px-3 py-2 text-sm">
              <div className="flex items-center justify-between">
                <p className="font-medium text-foreground">{row.valuation_name}</p>
                <span className="text-xs text-muted-foreground">{row.valuation_method}</span>
              </div>
              <div className="mt-1 grid grid-cols-2 gap-2 text-xs">
                <p className="text-muted-foreground">Enterprise Value</p>
                <p className="text-foreground">{formatINR(row.enterprise_value)}</p>
                <p className="text-muted-foreground">Equity Value</p>
                <p className="text-foreground">{formatINR(row.equity_value)}</p>
              </div>
            </div>
          ))}
          {valuations.length === 0 ? (
            <p className="text-sm text-muted-foreground">No valuations computed yet.</p>
          ) : null}
        </div>
      </article>
    </section>
  )
}
