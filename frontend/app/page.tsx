import Link from "next/link"
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"

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

export default async function LandingPage() {
  const session = await auth()
  if (session) {
    redirect("/dashboard")
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="flex items-center justify-between border-b border-gray-800 px-8 py-5">
        <span className="text-xl font-bold">FinanceOps</span>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm text-gray-400 hover:text-white">
            Sign in
          </Link>
          <Link href="/register" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700">
            Start free trial
          </Link>
        </div>
      </nav>
      <section className="mx-auto max-w-4xl px-8 py-24 text-center">
        <h1 className="mb-6 text-5xl font-bold leading-tight">
          Enterprise finance platform for the India mid-market
        </h1>
        <p className="mx-auto mb-10 max-w-2xl text-xl text-gray-400">
          MIS, consolidation, GST reconciliation, board packs, tax provision, debt covenants, and auditor portal in one platform.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/register" className="rounded-lg bg-blue-600 px-8 py-4 text-lg font-semibold hover:bg-blue-700">
            Start free trial
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-gray-700 px-8 py-4 font-medium text-gray-300 hover:border-gray-500"
          >
            Sign in to dashboard
          </Link>
        </div>
      </section>
      <section className="mx-auto grid max-w-5xl grid-cols-1 gap-6 px-8 pb-24 md:grid-cols-3">
        {FEATURES.map((feature) => (
          <div key={feature.title} className="rounded-xl border border-gray-800 bg-gray-900 p-6">
            <h3 className="mb-2 font-semibold text-white">{feature.title}</h3>
            <p className="text-sm text-gray-400">{feature.description}</p>
          </div>
        ))}
      </section>
      <footer className="flex items-center justify-between border-t border-gray-800 px-8 py-6 text-sm text-gray-500">
        <span>© 2026 FinanceOps</span>
        <div className="flex gap-6">
          <Link href="/legal/terms" className="hover:text-gray-300">
            Terms
          </Link>
          <Link href="/legal/privacy" className="hover:text-gray-300">
            Privacy
          </Link>
        </div>
      </footer>
    </div>
  )
}
