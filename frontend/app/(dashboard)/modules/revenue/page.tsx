"use client"

import { useState } from "react"
import { createRevenueContract, getRevenueSchedule } from "@/lib/api/modules"

type RevenueScheduleRow = {
  obligation_type: string
  period_number: number
  recognition_date: string
  revenue_amount: string
}

export default function RevenueModulePage() {
  const [entityId, setEntityId] = useState("")
  const [customerId, setCustomerId] = useState("CUSTOMER-001")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [contractValue, setContractValue] = useState("1200000")
  const [obligationType, setObligationType] = useState("LICENSE")
  const [contractId, setContractId] = useState("")
  const [journalId, setJournalId] = useState("")
  const [rows, setRows] = useState<RevenueScheduleRow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await createRevenueContract({
        entity_id: entityId,
        customer_id: customerId,
        contract_start_date: startDate,
        contract_end_date: endDate,
        contract_value: contractValue,
        obligations: [{ obligation_type: obligationType, allocation_value: contractValue }],
      }) as { contract_id: string; draft_journal_id: string }
      setContractId(response.contract_id)
      setJournalId(response.draft_journal_id)
      const schedule = await getRevenueSchedule(response.contract_id) as RevenueScheduleRow[]
      setRows(schedule)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revenue contract creation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Revenue Recognition Module</h1>
        <p className="text-sm text-muted-foreground">
          ASC 606 / IFRS 15 contract and performance obligation scheduling.
        </p>
      </header>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-3">
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Entity ID" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Customer ID" value={customerId} onChange={(e) => setCustomerId(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Contract value" value={contractValue} onChange={(e) => setContractValue(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Obligation type" value={obligationType} onChange={(e) => setObligationType(e.target.value)} />
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent md:col-span-3" type="button" onClick={() => void submit()} disabled={loading}>
          {loading ? "Generating..." : "Create Revenue Contract"}
        </button>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {contractId ? (
        <p className="text-sm text-muted-foreground">
          Contract ID: <span className="font-mono">{contractId}</span> | Draft Journal: <span className="font-mono">{journalId}</span>
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="rounded-lg border border-border bg-card">
          <table className="min-w-full text-sm">
            <thead className="border-b border-border bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left">Obligation</th>
                <th className="px-3 py-2 text-left">Period</th>
                <th className="px-3 py-2 text-left">Recognition Date</th>
                <th className="px-3 py-2 text-left">Revenue</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.obligation_type}-${row.period_number}`} className="border-b border-border/60">
                  <td className="px-3 py-2">{row.obligation_type}</td>
                  <td className="px-3 py-2">{row.period_number}</td>
                  <td className="px-3 py-2">{row.recognition_date}</td>
                  <td className="px-3 py-2">{row.revenue_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  )
}

