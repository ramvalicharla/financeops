"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { type StatutoryRegisterEntry } from "@/lib/types/sprint11"

export type RegisterTableProps = {
  registerType: string
  entries: StatutoryRegisterEntry[]
  onAddEntry?: (payload: {
    entry_date: string
    entry_description: string
    folio_number?: string | null
    amount?: string | null
    currency?: string | null
    reference_document?: string | null
  }) => Promise<void>
}

export function RegisterTable({ registerType, entries, onAddEntry }: RegisterTableProps) {
  const [showForm, setShowForm] = useState(false)
  const [entryDate, setEntryDate] = useState("")
  const [entryDescription, setEntryDescription] = useState("")
  const [folioNumber, setFolioNumber] = useState("")
  const [amount, setAmount] = useState("")
  const [currency, setCurrency] = useState("INR")
  const [referenceDocument, setReferenceDocument] = useState("")
  const [fieldErrors, setFieldErrors] = useState<{
    entryDate?: string
    entryDescription?: string
  }>({})

  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => (a.entry_date < b.entry_date ? 1 : -1)),
    [entries],
  )

  const handleSubmit = async (): Promise<void> => {
    if (!onAddEntry) {
      return
    }
    const nextFieldErrors: typeof fieldErrors = {}
    if (!entryDate) nextFieldErrors.entryDate = "Effective date is required."
    if (!entryDescription.trim()) nextFieldErrors.entryDescription = "Description is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    await onAddEntry({
      entry_date: entryDate,
      entry_description: entryDescription,
      folio_number: folioNumber || null,
      amount: amount || null,
      currency: amount ? currency : null,
      reference_document: referenceDocument || null,
    })
    setShowForm(false)
    setEntryDate("")
    setEntryDescription("")
    setFolioNumber("")
    setAmount("")
    setCurrency("INR")
    setReferenceDocument("")
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">{registerType}</p>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
          onClick={() => setShowForm((prev) => !prev)}
        >
          Add Entry
        </button>
      </div>
      {showForm ? (
        <div className="mt-3 grid gap-2 rounded-md border border-border/60 p-3 md:grid-cols-3">
          <FormField id="register-effective-date" label="Effective date" error={fieldErrors.entryDate} required>
            <Input type="date" value={entryDate} onChange={(event) => setEntryDate(event.target.value)} />
          </FormField>
          <FormField id="register-description" label="Description" error={fieldErrors.entryDescription} required>
            <Input
              value={entryDescription}
              onChange={(event) => setEntryDescription(event.target.value)}
            />
          </FormField>
          <FormField id="register-reference" label="Reference number">
            <Input
              value={folioNumber}
              onChange={(event) => setFolioNumber(event.target.value)}
            />
          </FormField>
          <FormField id="register-amount" label="Amount">
            <Input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="decimal"
            />
          </FormField>
          <FormField id="register-currency" label="Currency">
            <Input
              value={currency}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            />
          </FormField>
          <FormField id="register-reference-document" label="Reference document">
            <Input
              value={referenceDocument}
              onChange={(event) => setReferenceDocument(event.target.value)}
            />
          </FormField>
          <div className="md:col-span-3">
            <Button type="button" variant="outline" onClick={() => void handleSubmit()}>
              Save Entry
            </Button>
          </div>
        </div>
      ) : null}
      <table className="mt-3 w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Entry Date</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Description</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Folio</th>
            <th className="px-3 py-2 text-right text-xs text-muted-foreground">Amount</th>
            <th className="px-3 py-2 text-left text-xs text-muted-foreground">Reference</th>
          </tr>
        </thead>
        <tbody>
          {sortedEntries.map((entry) => (
            <tr key={entry.id} className="border-b border-border/60 last:border-0">
              <td className="px-3 py-2 text-foreground">{entry.entry_date}</td>
              <td className="px-3 py-2 text-foreground">{entry.entry_description}</td>
              <td className="px-3 py-2 text-foreground">{entry.folio_number ?? "-"}</td>
              <td className="px-3 py-2 text-right text-foreground">
                {entry.amount
                  ? `${entry.currency ?? "INR"} ${Number.parseFloat(entry.amount).toFixed(2)}`
                  : "-"}
              </td>
              <td className="px-3 py-2 text-foreground">
                {entry.reference_document ? (
                  <a
                    href={entry.reference_document}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-400 underline"
                  >
                    Open
                  </a>
                ) : (
                  "-"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
