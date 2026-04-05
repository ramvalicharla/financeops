import Link from "next/link"
import { Button } from "@/components/ui/button"
import { createMetadata } from "@/lib/metadata"

const FEATURES = [
  {
    title: "MIS & Consolidation",
    description: "Multi-entity consolidation with IAS 21, 60+ ratios, and board pack generation.",
  },
  {
    title: "India Compliance",
    description: "GST reconciliation, Form 3CEB transfer pricing, and MCA statutory registers.",
  },
  {
    title: "Director Signoff",
    description: "MFA-verified signoff with tamper-evident SHA256 certificates.",
  },
  {
    title: "Auditor Portal",
    description: "Token-based auditor access with PBC tracker and evidence workflows.",
  },
  {
    title: "Treasury & Forecasting",
    description: "13-week cash forecasting, covenants monitoring, and scenario modeling.",
  },
  {
    title: "Multi-GAAP",
    description: "INDAS, IFRS, US GAAP and Management views side by side.",
  },
]

export const metadata = createMetadata(
  "FinanceOps ? Enterprise Financial Operations Platform",
  "The financial operations platform built for 1B+ USD entities",
)

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="border-b border-border px-4 py-5 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <span className="text-xl font-semibold text-foreground">FinanceOps</span>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href="/login"
              className="text-sm text-muted-foreground transition hover:text-foreground"
            >
              Sign in
            </Link>
            <Button asChild>
              <Link href="/register">Start free trial</Link>
            </Button>
          </div>
        </div>
      </nav>
      <main id="main-content" className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-6 lg:px-8">
        <h1 className="mb-6 text-4xl font-semibold leading-tight text-foreground sm:text-5xl">
          Enterprise finance platform for the India mid-market
        </h1>
        <p className="mx-auto mb-10 max-w-2xl text-lg text-muted-foreground sm:text-xl">
          MIS, consolidation, GST reconciliation, board packs, tax provision, debt covenants, and auditor portal in one platform.
        </p>
        <div className="flex flex-col items-stretch justify-center gap-4 sm:flex-row sm:items-center">
          <Button
            asChild
            className="h-11 px-6 text-base sm:h-12 sm:px-8 sm:text-lg"
            size="lg"
          >
            <Link href="/register">Start free trial</Link>
          </Button>
          <Button
            asChild
            className="h-11 px-6 text-base sm:h-12 sm:px-8 sm:text-lg"
            size="lg"
            variant="outline"
          >
            <Link href="/login">Sign in to dashboard</Link>
          </Button>
        </div>

        <div className="mt-20 grid gap-6 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="rounded-xl border border-border bg-card p-6 text-left">
              <h2 className="mb-3 text-lg font-semibold text-foreground">{feature.title}</h2>
              <p className="text-sm leading-6 text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
