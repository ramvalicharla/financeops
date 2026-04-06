"use client"

import Link from "next/link"

const activationActions = [
  {
    title: "Upload Trial Balance",
    description: "Bring in your latest trial balance to activate reporting and mapping workflows.",
    href: "/setup/coa",
    cta: "Upload TB",
  },
  {
    title: "Connect ERP",
    description: "Connect Zoho Books or QuickBooks to start pulling ledger and account data.",
    href: "/sync/connect",
    cta: "Connect Zoho / QuickBooks",
  },
  {
    title: "Setup Mappings",
    description: "Review and confirm ERP-to-CoA mappings once your accounts or sync data are available.",
    href: "/settings/erp-mapping",
    cta: "Open mappings",
  },
] as const

export function DataActivationSection() {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-4 space-y-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Data Activation
        </h2>
        <p className="text-sm text-muted-foreground">
          Continue setup from the dashboard whenever you are ready to activate financial data.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {activationActions.map((action) => (
          <Link
            key={action.title}
            href={action.href}
            className="rounded-xl border border-border bg-background/40 p-4 transition hover:border-[hsl(var(--brand-primary))]"
          >
            <p className="text-base font-semibold text-foreground">{action.title}</p>
            <p className="mt-2 text-sm text-muted-foreground">{action.description}</p>
            <p className="mt-4 text-sm font-medium text-[hsl(var(--brand-primary))]">
              {action.cta} -&gt;
            </p>
          </Link>
        ))}
      </div>
    </section>
  )
}
