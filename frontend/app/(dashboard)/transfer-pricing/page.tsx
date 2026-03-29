"use client"

import Link from "next/link"
import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
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

  const load = async (): Promise<void> => {
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
  }

  useEffect(() => {
    void load()
  }, [])

  const addTransaction = async (): Promise<void> => {
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
          <Input value={party} onChange={(event) => setParty(event.target.value)} placeholder="Related party" />
          <Input value={country} onChange={(event) => setCountry(event.target.value.toUpperCase())} placeholder="ISO Country" />
          <Input
            value={transactionType}
            onChange={(event) => setTransactionType(event.target.value)}
            placeholder="Type"
          />
          <Input value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="Amount" />
          <Input value={method} onChange={(event) => setMethod(event.target.value)} placeholder="Method" />
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
