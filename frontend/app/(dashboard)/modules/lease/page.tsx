"use client"

import { useState } from "react"
import { createLease, getLeaseSchedule } from "@/lib/api/modules"

type LeaseScheduleRow = {
  period_number: number
  period_date: string
  opening_liability: string
  interest_expense: string
  lease_payment: string
  closing_liability: string
  rou_asset_value: string
  depreciation: string
}

export default function LeaseModulePage() {
  const [entityId, setEntityId] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [payment, setPayment] = useState("100000")
  const [discountRate, setDiscountRate] = useState("0.12")
  const [leaseType, setLeaseType] = useState("IFRS16")
  const [leaseId, setLeaseId] = useState("")
  const [journalId, setJournalId] = useState("")
  const [rows, setRows] = useState<LeaseScheduleRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await createLease({
        entity_id: entityId,
        lease_start_date: startDate,
        lease_end_date: endDate,
        lease_payment: payment,
        discount_rate: discountRate,
        lease_type: leaseType,
      }) as { lease_id: string; draft_journal_id: string }
      setLeaseId(response.lease_id)
      setJournalId(response.draft_journal_id)
      const schedule = await getLeaseSchedule(response.lease_id) as LeaseScheduleRow[]
      setRows(schedule)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lease creation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Lease Module</h1>
        <p className="text-sm text-muted-foreground">
          IFRS 16 / ASC 842 schedule generation with draft journal preview only.
        </p>
      </header>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-3">
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Entity ID" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Lease payment" value={payment} onChange={(e) => setPayment(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Annual discount rate (e.g. 0.12)" value={discountRate} onChange={(e) => setDiscountRate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Lease type" value={leaseType} onChange={(e) => setLeaseType(e.target.value)} />
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent md:col-span-3" type="button" onClick={() => void submit()} disabled={loading}>
          {loading ? "Generating..." : "Create Lease Schedule"}
        </button>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {leaseId ? (
        <p className="text-sm text-muted-foreground">
          Lease ID: <span className="font-mono">{leaseId}</span> | Draft Journal: <span className="font-mono">{journalId}</span>
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="rounded-lg border border-border bg-card">
          <table className="min-w-full text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left">Period</th>
                <th className="px-3 py-2 text-left">Date</th>
                <th className="px-3 py-2 text-left">Opening</th>
                <th className="px-3 py-2 text-left">Interest</th>
                <th className="px-3 py-2 text-left">Payment</th>
                <th className="px-3 py-2 text-left">Closing</th>
                <th className="px-3 py-2 text-left">ROU</th>
                <th className="px-3 py-2 text-left">Depreciation</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.period_number} className="border-b border-border/60">
                  <td className="px-3 py-2">{row.period_number}</td>
                  <td className="px-3 py-2">{row.period_date}</td>
                  <td className="px-3 py-2">{row.opening_liability}</td>
                  <td className="px-3 py-2">{row.interest_expense}</td>
                  <td className="px-3 py-2">{row.lease_payment}</td>
                  <td className="px-3 py-2">{row.closing_liability}</td>
                  <td className="px-3 py-2">{row.rou_asset_value}</td>
                  <td className="px-3 py-2">{row.depreciation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  )
}

