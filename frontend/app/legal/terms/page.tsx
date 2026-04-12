import Link from "next/link"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Terms of Service")

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="mb-2 text-3xl font-semibold text-foreground">Terms of Service</h1>
      <p className="mb-10 text-sm text-muted-foreground">Last updated: March 2026</p>
      <div className="space-y-8 text-foreground">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">1. Acceptance of Terms</h2>
          <p>By using Finqor you agree to these terms. If acting for an organisation, you confirm authority to bind it.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">2. Description of Service</h2>
          <p>Finqor provides finance operations SaaS including MIS, reconciliation, consolidation, compliance and reporting workflows.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">3. User Accounts &amp; Security</h2>
          <p>You must protect credentials, enable MFA where required, and notify us of unauthorised access.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">4. Data Ownership &amp; Privacy</h2>
          <p>You own customer data. Processing follows our Privacy Policy and applicable Indian law including the DPDP Act, 2023.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">5. Acceptable Use</h2>
          <p>You must not process unlawful data, attempt cross-tenant access, reverse engineer the platform, or abuse APIs.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">6. Financial Data Disclaimer</h2>
          <p>Outputs are decision-support only and not legal/tax advice. Qualified professionals must review statutory and filing outputs.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">7. Service Availability &amp; SLA</h2>
          <p>
            Target uptime is 99.5% monthly. See{" "}
            <Link href="/legal/sla" className="text-foreground underline-offset-4 transition hover:underline">
              Service Level Agreement
            </Link>
            .
          </p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">8. Payment &amp; Credits</h2>
          <p>Some features consume credits. Subscription/credit terms apply per billing policy and law.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">9. Termination</h2>
          <p>Either party may terminate with notice. Data export is available for a limited post-termination period.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">10. Governing Law</h2>
          <p>These terms are governed by Indian law. Courts in India have jurisdiction.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">11. Contact</h2>
          <p>legal@financeops.in</p>
        </section>
      </div>
    </div>
  )
}
