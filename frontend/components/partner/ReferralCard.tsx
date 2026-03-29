"use client"

import type { ReferralTrackingRow } from "@/lib/types/partner"

interface ReferralCardProps {
  referral: ReferralTrackingRow
}

const statusClass: Record<ReferralTrackingRow["status"], string> = {
  clicked: "border-border text-muted-foreground",
  signed_up: "border-blue-300/50 text-blue-200",
  converted: "border-emerald-300/50 text-emerald-200",
  churned: "border-[hsl(var(--brand-danger)/0.5)] text-[hsl(var(--brand-danger))]",
  expired: "border-amber-300/60 text-amber-200",
}

export function ReferralCard({ referral }: ReferralCardProps) {
  const expiry = new Date(referral.expires_at).getTime()
  const now = Date.now()
  const daysRemaining = Math.max(0, Math.ceil((expiry - now) / (24 * 60 * 60 * 1000)))

  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{referral.referral_email ?? "Anonymous referral"}</h3>
          <p className="text-xs text-muted-foreground">Code: {referral.referral_code}</p>
        </div>
        <span className={`rounded-full border px-2 py-0.5 text-xs ${statusClass[referral.status]}`}>
          {referral.status}
        </span>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
        <p>Clicked: {referral.clicked_at.slice(0, 10)}</p>
        <p>Days to expiry: {referral.status === "converted" ? "converted" : daysRemaining}</p>
        <p>Signed up: {referral.signed_up_at ? referral.signed_up_at.slice(0, 10) : "-"}</p>
        <p>Converted: {referral.converted_at ? referral.converted_at.slice(0, 10) : "-"}</p>
      </div>

      {referral.first_payment_amount ? (
        <p className="mt-2 text-xs text-foreground">First payment: {referral.first_payment_amount}</p>
      ) : null}
    </article>
  )
}
