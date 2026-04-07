"use client"

import { useEffect, useMemo, useState } from "react"
import { ComplianceCalendar } from "@/components/statutory/ComplianceCalendar"
import { RegisterTable } from "@/components/statutory/RegisterTable"
import {
  addStatutoryRegisterEntry,
  getStatutoryCalendar,
  getStatutoryRegister,
  markStatutoryFiled,
} from "@/lib/api/sprint11"
import { type StatutoryCalendarItem, type StatutoryRegisterEntry } from "@/lib/types/sprint11"

const registerTypes = [
  "members",
  "directors",
  "charges",
  "debentures",
  "contracts",
  "investments",
  "loans",
  "related_party",
  "share_transfers",
  "buy_back",
  "deposits",
  "significant_beneficial_owners",
] as const

export default function StatutoryPage() {
  const fiscalYear = new Date().getFullYear()
  const [calendar, setCalendar] = useState<StatutoryCalendarItem[]>([])
  const [activeRegister, setActiveRegister] =
    useState<(typeof registerTypes)[number]>("members")
  const [entries, setEntries] = useState<StatutoryRegisterEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const overdueCount = useMemo(
    () => calendar.filter((row) => row.is_overdue).length,
    [calendar],
  )

  const loadCalendar = async (): Promise<void> => {
    const rows = await getStatutoryCalendar(fiscalYear)
    setCalendar(rows)
  }

  const loadRegister = async (registerType: string): Promise<void> => {
    const payload = await getStatutoryRegister(registerType, {
      limit: 100,
      offset: 0,
    })
    setEntries(payload.data)
  }

  const loadAll = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([loadCalendar(), loadRegister(activeRegister)])
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load statutory data")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
  }, [])

  useEffect(() => {
    void loadRegister(activeRegister)
  }, [activeRegister])

  const markFiled = async (filingId: string): Promise<void> => {
    try {
      await markStatutoryFiled(filingId, {
        filed_date: new Date().toISOString().slice(0, 10),
        filing_reference: `REF-${Date.now()}`,
      })
      await loadCalendar()
    } catch (markError) {
      setError(markError instanceof Error ? markError.message : "Failed to mark filing")
    }
  }

  const addEntry = async (payload: {
    entry_date: string
    entry_description: string
    folio_number?: string | null
    amount?: string | null
    currency?: string | null
    reference_document?: string | null
  }): Promise<void> => {
    try {
      await addStatutoryRegisterEntry(activeRegister, payload)
      await loadRegister(activeRegister)
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Failed to add register entry")
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Statutory Compliance</h1>
      <p className="text-sm text-muted-foreground">Overdue filings: {overdueCount}</p>
      {loading ? <p className="text-sm text-muted-foreground">Loading compliance data...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <ComplianceCalendar items={calendar} onMarkFiled={markFiled} />

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-3 flex flex-wrap gap-2">
          {registerTypes.map((registerType) => (
            <button
              key={registerType}
              type="button"
              onClick={() => setActiveRegister(registerType)}
              className={`rounded-md border px-2 py-1 text-xs ${
                activeRegister === registerType
                  ? "border-[hsl(var(--brand-primary))] text-foreground"
                  : "border-border text-muted-foreground"
              }`}
            >
              {registerType}
            </button>
          ))}
        </div>
        <RegisterTable registerType={activeRegister} entries={entries} onAddEntry={addEntry} />
      </section>
    </div>
  )
}
