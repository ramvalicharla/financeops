"use client"

import { useState } from "react"
import { createAccrualSchedule, createPrepaidSchedule } from "@/lib/api/modules"

export default function PrepaidAccrualModulePage() {
  const [entityId, setEntityId] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [amount, setAmount] = useState("120000")
  const [prepaidName, setPrepaidName] = useState("Insurance Premium")
  const [accrualName, setAccrualName] = useState("Month End Accrual")
  const [result, setResult] = useState<string>("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const runPrepaid = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await createPrepaidSchedule({
        entity_id: entityId,
        prepaid_name: prepaidName,
        start_date: startDate,
        end_date: endDate,
        total_amount: amount,
      }) as { schedule_batch_id: string; draft_journal_id: string; periods: number }
      setResult(
        `Prepaid batch ${response.schedule_batch_id} created (${response.periods} periods), draft journal ${response.draft_journal_id}.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Prepaid creation failed")
    } finally {
      setLoading(false)
    }
  }

  const runAccrual = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await createAccrualSchedule({
        entity_id: entityId,
        accrual_name: accrualName,
        start_date: startDate,
        end_date: endDate,
        total_amount: amount,
      }) as { schedule_batch_id: string; draft_journal_id: string; periods: number }
      setResult(
        `Accrual batch ${response.schedule_batch_id} created (${response.periods} periods), draft journal ${response.draft_journal_id}.`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Accrual creation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Prepaid & Accrual Module</h1>
        <p className="text-sm text-muted-foreground">
          Generate time-based prepaid and accrual schedules with draft-only journals.
        </p>
      </header>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-3">
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Entity ID" value={entityId} onChange={(e) => setEntityId(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Prepaid name" value={prepaidName} onChange={(e) => setPrepaidName(e.target.value)} />
        <input className="rounded-md border border-border bg-background px-3 py-2" placeholder="Accrual name" value={accrualName} onChange={(e) => setAccrualName(e.target.value)} />
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent" type="button" onClick={() => void runPrepaid()} disabled={loading}>
          {loading ? "Working..." : "Create Prepaid Schedule"}
        </button>
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent" type="button" onClick={() => void runAccrual()} disabled={loading}>
          {loading ? "Working..." : "Create Accrual Schedule"}
        </button>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {result ? <p className="text-sm text-muted-foreground">{result}</p> : null}
    </main>
  )
}

