"use client"

import Link from "next/link"
import { InvoiceTable } from "@/components/billing/InvoiceTable"
import { useInvoices } from "@/hooks/useBilling"

export default function BillingInvoicesPage() {
  const invoicesQuery = useInvoices()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Invoices</h1>
        <Link
          href="/settings/billing"
          className="rounded-md border border-border px-3 py-2 text-sm hover:bg-accent"
        >
          Back to Billing
        </Link>
      </div>

      {invoicesQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading invoices...</p>
      ) : null}
      {invoicesQuery.isError ? (
        <p className="text-sm text-destructive">Failed to load invoices.</p>
      ) : null}

      <InvoiceTable invoices={invoicesQuery.data ?? []} />
    </div>
  )
}

