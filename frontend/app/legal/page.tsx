import Link from "next/link"

export default function LegalIndexPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="mb-4 text-3xl font-bold text-white">Legal</h1>
      <p className="mb-6 text-gray-300">Policies and agreements applicable to FinanceOps use.</p>
      <ul className="space-y-3 text-blue-400">
        <li><Link href="/legal/terms">Terms of Service</Link></li>
        <li><Link href="/legal/privacy">Privacy Policy</Link></li>
        <li><Link href="/legal/dpa">Data Processing Agreement</Link></li>
        <li><Link href="/legal/sla">Service Level Agreement</Link></li>
        <li><Link href="/legal/cookies">Cookie Policy</Link></li>
      </ul>
    </div>
  )
}

