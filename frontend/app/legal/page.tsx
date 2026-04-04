import Link from "next/link"

export default function LegalIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="mb-4 text-3xl font-semibold text-foreground">Legal</h1>
      <p className="mb-6 text-muted-foreground">Policies and agreements applicable to FinanceOps use.</p>
      <ul className="space-y-3">
        <li>
          <Link href="/legal/terms" className="text-foreground underline-offset-4 transition hover:underline">
            Terms of Service
          </Link>
        </li>
        <li>
          <Link href="/legal/privacy" className="text-foreground underline-offset-4 transition hover:underline">
            Privacy Policy
          </Link>
        </li>
        <li>
          <Link href="/legal/dpa" className="text-foreground underline-offset-4 transition hover:underline">
            Data Processing Agreement
          </Link>
        </li>
        <li>
          <Link href="/legal/sla" className="text-foreground underline-offset-4 transition hover:underline">
            Service Level Agreement
          </Link>
        </li>
        <li>
          <Link href="/legal/cookies" className="text-foreground underline-offset-4 transition hover:underline">
            Cookie Policy
          </Link>
        </li>
      </ul>
    </div>
  )
}
