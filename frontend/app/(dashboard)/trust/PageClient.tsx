"use client"

import { useCallback, useEffect, useState } from "react"
import { getConsentSummary, getSoc2Dashboard, listBreaches } from "@/lib/api/compliance"
import type { ComplianceDashboard, ConsentSummary } from "@/lib/types/compliance"
import type { GDPRBreach } from "@/lib/types/compliance"
import { TrustSummaryCard } from "@/components/trust/TrustSummaryCard"

export default function TrustHubPage() {
  const [soc2, setSoc2] = useState<ComplianceDashboard | null>(null)
  const [consent, setConsent] = useState<ConsentSummary | null>(null)
  const [breaches, setBreaches] = useState<GDPRBreach[]>([])

  useEffect(() => {
    const load = async () => {
      const [soc2Data, consentData, breachesData] = await Promise.all([
        getSoc2Dashboard(),
        getConsentSummary(),
        listBreaches({ limit: 50, offset: 0 }),
      ])
      setSoc2(soc2Data)
      setConsent(consentData)
      setBreaches(breachesData.data)
    }
    void load()
  }, [])

  const coveragePct =
    consent && consent.consent.length > 0
      ? (
          (consent.consent.reduce((acc, row) => acc + Number.parseFloat(row.coverage_pct), 0) /
            consent.consent.length) *
          100
        ).toFixed(1)
      : "0.0"

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Trust Hub</h1>
        <p className="text-sm text-muted-foreground">Read-only compliance posture and GDPR operations for auditors.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <TrustSummaryCard
          title="SOC2 Status"
          subtitle="This platform is SOC2 monitored continuously."
          rag={soc2?.overall_rag ?? "grey"}
          stats={`${soc2?.summary.green ?? 0}/47 controls green`}
          href="/trust/soc2"
        />
        <TrustSummaryCard
          title="GDPR Compliance"
          subtitle="Consent coverage and breach governance."
          rag={breaches.some((row) => row.status === "open") ? "amber" : "green"}
          stats={`Coverage ${coveragePct}% | Breaches ${breaches.length}`}
          href="/trust/gdpr"
        />
        <TrustSummaryCard
          title="Data Rights"
          subtitle="Your users can request and export their data."
          rag="green"
          stats="Self-service portability available"
          href="/trust/gdpr/consent"
        />
      </section>
    </div>
  )
}

