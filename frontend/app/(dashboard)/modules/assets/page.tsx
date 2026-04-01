"use client"

import { useState } from "react"
import { createFixedAsset, getAssetSchedule } from "@/lib/api/modules"

type AssetScheduleRow = {
  period_number: number
  period_date: string
  depreciation: string
  net_book_value: string
}

export default function AssetsModulePage() {
  const [entityId, setEntityId] = useState("")
  const [assetName, setAssetName] = useState("Computer Equipment")
  const [cost, setCost] = useState("500000")
  const [lifeYears, setLifeYears] = useState(3)
  const [method, setMethod] = useState<"SLM" | "WDV">("SLM")
  const [assetId, setAssetId] = useState("")
  const [journalId, setJournalId] = useState("")
  const [rows, setRows] = useState<AssetScheduleRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await createFixedAsset({
        entity_id: entityId,
        asset_name: assetName,
        cost,
        useful_life_years: lifeYears,
        depreciation_method: method,
      }) as { asset_id: string; draft_journal_id: string }
      setAssetId(response.asset_id)
      setJournalId(response.draft_journal_id)
      const schedule = await getAssetSchedule(response.asset_id) as AssetScheduleRow[]
      setRows(schedule)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fixed asset creation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Fixed Assets Module</h1>
        <p className="text-sm text-muted-foreground">
          IAS 16 depreciation schedule generation with draft capitalization journal.
        </p>
      </header>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-3">
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Entity ID" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Asset name" value={assetName} onChange={(e) => setAssetName(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Cost" value={cost} onChange={(e) => setCost(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="number" min={1} value={lifeYears} onChange={(e) => setLifeYears(Number(e.target.value))} />
        <select className="rounded-md border border-border bg-background px-3 py-2" value={method} onChange={(e) => setMethod(e.target.value as "SLM" | "WDV")}>
          <option value="SLM">SLM</option>
          <option value="WDV">WDV</option>
        </select>
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent" type="button" onClick={() => void submit()} disabled={loading}>
          {loading ? "Generating..." : "Create Asset Schedule"}
        </button>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {assetId ? (
        <p className="text-sm text-muted-foreground">
          Asset ID: <span className="font-mono">{assetId}</span> | Draft Journal: <span className="font-mono">{journalId}</span>
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="rounded-lg border border-border bg-card">
          <table className="min-w-full text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left">Period</th>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-left">Depreciation</th>
                <th className="px-3 py-2 text-left">NBV</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.period_number} className="border-b border-border/60">
                  <td className="px-3 py-2">{row.period_number}</td>
                  <td className="px-3 py-2">{row.period_date}</td>
                  <td className="px-3 py-2">{row.depreciation}</td>
                  <td className="px-3 py-2">{row.net_book_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  )
}

