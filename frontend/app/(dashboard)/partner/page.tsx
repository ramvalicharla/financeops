"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { getPartnerDashboard, registerPartner } from "@/lib/api/partner"
import type { PartnerDashboard as PartnerDashboardPayload } from "@/lib/types/partner"
import { PartnerDashboard } from "@/components/partner/PartnerDashboard"

export default function PartnerHubPage() {
  const [dashboard, setDashboard] = useState<PartnerDashboardPayload | null>(null)
  const [tier, setTier] = useState<"referral" | "reseller" | "technology">("referral")
  const [companyName, setCompanyName] = useState("")
  const [contactEmail, setContactEmail] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = async () => {
    try {
      const payload = await getPartnerDashboard()
      setDashboard(payload)
    } catch {
      setDashboard(null)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const submitRegistration = async () => {
    setError(null)
    setMessage(null)
    try {
      await registerPartner({
        partner_tier: tier,
        company_name: companyName,
        contact_email: contactEmail,
        website_url: websiteUrl || undefined,
      })
      setMessage("Partner application submitted. Await platform approval.")
      await load()
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to register as partner")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Partner Program</h1>
        <p className="text-sm text-muted-foreground">
          Track referrals and commissions across referral, reseller, and technology tiers.
        </p>
      </header>

      {dashboard ? (
        <PartnerDashboard dashboard={dashboard} />
      ) : (
        <>
          <section className="grid gap-3 md:grid-cols-3">
            <article className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Referral</h2>
              <p className="mt-2 text-xs text-muted-foreground">15% of first-year payment from converted referrals.</p>
            </article>
            <article className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Reseller</h2>
              <p className="mt-2 text-xs text-muted-foreground">30% recurring commission for managed client subscriptions.</p>
            </article>
            <article className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Technology</h2>
              <p className="mt-2 text-xs text-muted-foreground">10% share for ecosystem integrations that drive revenue.</p>
            </article>
          </section>

          <section className="rounded-xl border border-border bg-card p-4">
            <h2 className="text-sm font-semibold text-foreground">Become a Partner</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <select
                value={tier}
                onChange={(event) => setTier(event.target.value as "referral" | "reseller" | "technology")}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="referral">Referral</option>
                <option value="reseller">Reseller</option>
                <option value="technology">Technology</option>
              </select>
              <input
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                placeholder="Company name"
              />
              <input
                value={contactEmail}
                onChange={(event) => setContactEmail(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                placeholder="Contact email"
              />
              <input
                value={websiteUrl}
                onChange={(event) => setWebsiteUrl(event.target.value)}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                placeholder="Website URL (optional)"
              />
              <button
                type="button"
                onClick={() => void submitRegistration()}
                className="w-fit rounded-md border border-border px-3 py-2 text-sm text-foreground"
              >
                Submit Application
              </button>
            </div>
          </section>
        </>
      )}

      <section className="flex gap-2">
        <Link href="/partner/referrals" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Referrals
        </Link>
        <Link href="/partner/earnings" className="rounded-md border border-border px-3 py-2 text-sm text-foreground">
          Earnings
        </Link>
      </section>

      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
    </div>
  )
}
