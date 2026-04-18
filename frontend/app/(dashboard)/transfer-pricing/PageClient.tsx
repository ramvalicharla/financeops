"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"
import { ICTransactionTable } from "@/components/transfer_pricing/ICTransactionTable"
import {
  addICTransaction,
  generateForm3CEB,
  getTransferPricingApplicability,
  listICTransactions,
  listTransferPricingDocs,
} from "@/lib/api/sprint11"
import { type ICTransaction, type TransferPricingApplicability, type TransferPricingDoc } from "@/lib/types/sprint11"

const fiscalYear = new Date().getFullYear()

export default function TransferPricingPage() {
  const [applicability, setApplicability] = useState<TransferPricingApplicability | null>(null)
  const [transactions, setTransactions] = useState<ICTransaction[]>([])
  const [documents, setDocuments] = useState<TransferPricingDoc[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  const [party, setParty] = useState("")
  const [country, setCountry] = useState("IND")
  const [transactionType, setTransactionType] = useState("services")
  const [amount, setAmount] = useState("0")
  const [method, setMethod] = useState("TNMM")
  const [fieldErrors, setFieldErrors] = useState<{
    party?: string
    country?: string
    transactionType?: string
    amount?: string
    method?: string
  }>({})

  const load = useCallback(async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const [applicabilityPayload, transactionPayload, documentPayload] = await Promise.all([
        getTransferPricingApplicability(fiscalYear),
        listICTransactions({ fiscal_year: fiscalYear, limit: 200, offset: 0 }),
        listTransferPricingDocs({ limit: 100, offset: 0 }),
      ])
      setApplicability(applicabilityPayload)
      setTransactions(transactionPayload.data)
      setDocuments(documentPayload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load transfer pricing data")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const addTransaction = async (): Promise<void> => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!party.trim()) nextFieldErrors.party = "Related party is required."
    if (!country.trim()) nextFieldErrors.country = "Country is required."
    if (!transactionType.trim()) nextFieldErrors.transactionType = "Transaction type is required."
    if (!amount.trim()) nextFieldErrors.amount = "Amount is required."
    if (!method.trim()) nextFieldErrors.method = "Pricing method is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      setError(null)
      return
    }
    setFieldErrors({})
    setError(null)
    try {
      await addICTransaction({
        fiscal_year: fiscalYear,
        transaction_type: transactionType,
        related_party_name: party,
        related_party_country: country,
        transaction_amount: amount,
        pricing_method: method,
        is_international: true,
      })
      setParty("")
      setAmount("0")
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to add transaction")
    }
  }

  const generate3CEB = async (): Promise<void> => {
    setGenerating(true)
    setError(null)
    try {
      await generateForm3CEB(fiscalYear)
      await load()
    } catch (genError) {
      setError(genError instanceof Error ? genError.message : "Failed to generate Form 3CEB")
    } finally {
      setGenerating(false)
    }
  }

  const transactionSummary = useMemo(() => transactions.slice(0, 10), [transactions])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Transfer Pricing</h1>
      <p className="text-sm text-muted-foreground">
        Intercompany transaction registry and Form 3CEB generation.
      </p>

      {applicability ? (
        <section
          className={`rounded-xl border p-4 ${
            applicability.is_required
              ? "border-amber-500/40 bg-amber-500/10"
              : "border-emerald-500/40 bg-emerald-500/10"
          }`}
        >
          <p className="font-medium text-foreground">
            {applicability.is_required
              ? "Required — Form 3CEB must be filed"
              : "Not Required — no filing needed for this year"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">{applicability.reason}</p>
        </section>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Add Transaction</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-5">
          <FormField id="tp-related-party" label="Related party" error={fieldErrors.party} required>
            <Input value={party} onChange={(event) => setParty(event.target.value)} />
          </FormField>
          <FormField id="tp-country" label="Country" error={fieldErrors.country} required>
            <Input value={country} onChange={(event) => setCountry(event.target.value.toUpperCase())} />
          </FormField>
          <FormField id="tp-transaction-type" label="Transaction type" error={fieldErrors.transactionType} required>
            <Input
              value={transactionType}
              onChange={(event) => setTransactionType(event.target.value)}
            />
          </FormField>
          <FormField id="tp-amount" label="Amount" error={fieldErrors.amount} required>
            <Input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" />
          </FormField>
          <FormField id="tp-method" label="Pricing method" error={fieldErrors.method} required>
            <Input value={method} onChange={(event) => setMethod(event.target.value)} />
          </FormField>
        </div>
        <Button className="mt-3" variant="outline" onClick={() => void addTransaction()}>
          Add Transaction
        </Button>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <Button variant="outline" onClick={() => void generate3CEB()} disabled={generating}>
          {generating ? "Generating..." : "Generate Form 3CEB"}
        </Button>
      </section>

      {loading ? <p className="text-sm text-muted-foreground">Loading transfer pricing data...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <ICTransactionTable rows={transactionSummary} />

      <section className="space-y-2 rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Documents</h2>
        {documents.map((doc) => (
          <Link
            key={doc.id}
            href={`/transfer-pricing/${doc.id}`}
            className="block rounded-md border border-border/60 px-3 py-2 text-sm text-foreground"
          >
            {doc.document_type} · FY {doc.fiscal_year} · v{doc.version}
          </Link>
        ))}
      </section>
    </div>
  )
}
