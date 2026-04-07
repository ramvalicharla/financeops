"use client"

import { useState } from "react"
import { FormField } from "@/components/ui/FormField"
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
    <section aria-label="Prepaid and accrual module" className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">Prepaid & Accrual Module</h1>
        <p className="text-sm text-muted-foreground">
          Generate time-based prepaid and accrual schedules with draft-only journals.
        </p>
      </header>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-3">
        <FormField id="prepaid-entity-id" label="Entity ID"><input className="rounded-md border border-border bg-background px-3 py-2" value={entityId} onChange={(e) => setEntityId(e.target.value)} /></FormField>
        <FormField id="prepaid-start-date" label="Start date"><input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></FormField>
        <FormField id="prepaid-end-date" label="End date"><input className="rounded-md border border-border bg-background px-3 py-2" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></FormField>
        <FormField id="prepaid-amount" label="Amount"><input className="rounded-md border border-border bg-background px-3 py-2" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" /></FormField>
        <FormField id="prepaid-name" label="Prepaid name"><input className="rounded-md border border-border bg-background px-3 py-2" value={prepaidName} onChange={(e) => setPrepaidName(e.target.value)} /></FormField>
        <FormField id="prepaid-accrual-name" label="Accrual name"><input className="rounded-md border border-border bg-background px-3 py-2" value={accrualName} onChange={(e) => setAccrualName(e.target.value)} /></FormField>
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent" type="button" onClick={() => void runPrepaid()} disabled={loading}>
          {loading ? "Working..." : "Create Prepaid Schedule"}
        </button>
        <button className="rounded-md border border-border px-3 py-2 hover:bg-accent" type="button" onClick={() => void runAccrual()} disabled={loading}>
          {loading ? "Working..." : "Create Accrual Schedule"}
        </button>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {result ? <p className="text-sm text-muted-foreground">{result}</p> : null}
    </section>
  )
}
