export default function DPAPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="mb-2 text-3xl font-semibold text-foreground">Data Processing Agreement</h1>
      <p className="mb-10 text-sm text-muted-foreground">This DPA forms part of the Terms of Service between FinanceOps and Customer.</p>
      <div className="space-y-8 text-foreground">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">1. Definitions</h2>
          <p>Customer Data, Processing, and Sub-processor terms follow DPDP Act context and contractual definitions.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">2. Processing Instructions</h2>
          <p>FinanceOps processes customer data only on documented customer instructions in the product contract.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">3. Security Measures</h2>
          <p>AES-256-GCM at rest, TLS in transit, MFA controls, tenant isolation with RLS, and security monitoring.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">4. Sub-processors</h2>
          <p>Infrastructure, email, and approved AI providers are used under contractual controls and least-data principles.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">5. Breach Notification</h2>
          <p>FinanceOps will notify customer contacts within contractual timelines with incident details and mitigation actions.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">6. Audit Rights</h2>
          <p>Compliance artifacts and independent assurance evidence are available subject to confidentiality obligations.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">7. Deletion of Data</h2>
          <p>On termination, customer data deletion/export follows contract and legal retention requirements.</p>
        </section>
      </div>
    </div>
  )
}
