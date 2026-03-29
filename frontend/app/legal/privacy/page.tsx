export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="mb-2 text-3xl font-bold text-white">Privacy Policy</h1>
      <p className="mb-10 text-sm text-gray-400">
        Last updated: March 2026. Compliant with the Digital Personal Data Protection Act, 2023 (India).
      </p>
      <div className="space-y-8 text-gray-300">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">1. Data Controller</h2>
          <p>FinanceOps acts as Data Fiduciary under the DPDP Act, 2023 for customer account and platform operations data.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">2. Data We Collect</h2>
          <p>Account details, uploaded finance records, usage/security telemetry, and device metadata required for service delivery.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">3. How We Use Data</h2>
          <p>We use data to run the platform, send operational notices, improve quality via anonymised analytics, and satisfy legal obligations.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">4. Data Localisation</h2>
          <p>Indian customer personal and financial data is stored in India; any external processing uses masked data and lawful controls.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">5. Your DPDP Rights</h2>
          <p>Access, correction, erasure, grievance redressal, and nomination requests can be raised via Privacy settings or privacy@financeops.in.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">6. Data Retention</h2>
          <p>Operational and statutory retention schedules apply (financial records up to 8 years; account and audit retention as configured).</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">7. Cookies</h2>
          <p>
            We use essential security/authentication cookies only. See{" "}
            <a href="/legal/cookies" className="text-blue-400 hover:underline">
              Cookie Policy
            </a>
            .
          </p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">8. Grievance Officer</h2>
          <p>grievance@financeops.in</p>
        </section>
      </div>
    </div>
  )
}

