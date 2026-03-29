export default function SLAPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="mb-2 text-3xl font-bold text-white">Service Level Agreement</h1>
      <p className="mb-10 text-sm text-gray-400">Effective from account activation date.</p>
      <div className="space-y-8 text-gray-300">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">1. Uptime Commitment</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-white">
                  <th className="py-2 text-left">Plan</th>
                  <th className="py-2 text-left">Monthly Uptime</th>
                  <th className="py-2 text-left">Max Downtime/Month</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr><td className="py-3">Starter</td><td className="py-3">99.0%</td><td className="py-3">7.2 hours</td></tr>
                <tr><td className="py-3">Professional</td><td className="py-3">99.5%</td><td className="py-3">3.6 hours</td></tr>
                <tr><td className="py-3">Enterprise</td><td className="py-3">99.9%</td><td className="py-3">43.8 minutes</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">2. Support Response Times</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-white">
                  <th className="py-2 text-left">Severity</th>
                  <th className="py-2 text-left">Description</th>
                  <th className="py-2 text-left">First Response</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr><td className="py-3 text-red-400">Critical</td><td className="py-3">Platform unavailable</td><td className="py-3">2 hours</td></tr>
                <tr><td className="py-3 text-amber-400">High</td><td className="py-3">Core feature broken</td><td className="py-3">8 hours</td></tr>
                <tr><td className="py-3 text-blue-400">Medium</td><td className="py-3">Feature degraded</td><td className="py-3">24 hours</td></tr>
                <tr><td className="py-3 text-gray-400">Low</td><td className="py-3">General enquiry</td><td className="py-3">48 hours</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">3. Service Credits</h2>
          <p>Credits are applied to future invoices when uptime falls below committed levels according to policy bands.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">4. Exclusions</h2>
          <p>Planned maintenance, force majeure, and customer-caused outages are excluded from SLA calculations.</p>
        </section>
      </div>
    </div>
  )
}

