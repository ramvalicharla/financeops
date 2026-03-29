export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="mb-2 text-3xl font-bold text-white">Terms of Service</h1>
      <p className="mb-10 text-sm text-gray-400">Last updated: March 2026</p>
      <div className="space-y-8 text-gray-300">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">1. Acceptance of Terms</h2>
          <p>By using FinanceOps you agree to these terms. If acting for an organisation, you confirm authority to bind it.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">2. Description of Service</h2>
          <p>FinanceOps provides finance operations SaaS including MIS, reconciliation, consolidation, compliance and reporting workflows.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">3. User Accounts &amp; Security</h2>
          <p>You must protect credentials, enable MFA where required, and notify us of unauthorised access.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">4. Data Ownership &amp; Privacy</h2>
          <p>You own customer data. Processing follows our Privacy Policy and applicable Indian law including the DPDP Act, 2023.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">5. Acceptable Use</h2>
          <p>You must not process unlawful data, attempt cross-tenant access, reverse engineer the platform, or abuse APIs.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">6. Financial Data Disclaimer</h2>
          <p>Outputs are decision-support only and not legal/tax advice. Qualified professionals must review statutory and filing outputs.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">7. Service Availability &amp; SLA</h2>
          <p>
            Target uptime is 99.5% monthly. See{" "}
            <a href="/legal/sla" className="text-blue-400 hover:underline">
              Service Level Agreement
            </a>
            .
          </p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">8. Payment &amp; Credits</h2>
          <p>Some features consume credits. Subscription/credit terms apply per billing policy and law.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">9. Termination</h2>
          <p>Either party may terminate with notice. Data export is available for a limited post-termination period.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">10. Governing Law</h2>
          <p>These terms are governed by Indian law. Courts in India have jurisdiction.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">11. Contact</h2>
          <p>legal@financeops.in</p>
        </section>
      </div>
    </div>
  )
}

