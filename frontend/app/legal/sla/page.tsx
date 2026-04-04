import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Service Level Agreement")

export default function SLAPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="mb-2 text-3xl font-semibold text-foreground">Service Level Agreement</h1>
      <p className="mb-10 text-sm text-muted-foreground">Effective from account activation date.</p>
      <div className="space-y-8 text-foreground">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">1. Uptime Commitment</h2>
          <div className="overflow-x-auto">
            <table aria-label="Service level commitments" className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-foreground">
                  <th scope="col" className="py-2 text-left">Plan</th>
                  <th scope="col" className="py-2 text-left">Monthly Uptime</th>
                  <th scope="col" className="py-2 text-left">Max Downtime/Month</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr><td className="py-3">Starter</td><td className="py-3">99.0%</td><td className="py-3">7.2 hours</td></tr>
                <tr><td className="py-3">Professional</td><td className="py-3">99.5%</td><td className="py-3">3.6 hours</td></tr>
                <tr><td className="py-3">Enterprise</td><td className="py-3">99.9%</td><td className="py-3">43.8 minutes</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">2. Support Response Times</h2>
          <div className="overflow-x-auto">
            <table aria-label="Service level commitments" className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-foreground">
                  <th scope="col" className="py-2 text-left">Severity</th>
                  <th scope="col" className="py-2 text-left">Description</th>
                  <th scope="col" className="py-2 text-left">First Response</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr><td className="py-3 text-[hsl(var(--brand-danger))]">Critical</td><td className="py-3">Platform unavailable</td><td className="py-3">2 hours</td></tr>
                <tr><td className="py-3 text-[hsl(var(--brand-warning))]">High</td><td className="py-3">Core feature broken</td><td className="py-3">8 hours</td></tr>
                <tr><td className="py-3 text-foreground">Medium</td><td className="py-3">Feature degraded</td><td className="py-3">24 hours</td></tr>
                <tr><td className="py-3 text-muted-foreground">Low</td><td className="py-3">General enquiry</td><td className="py-3">48 hours</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">3. Service Credits</h2>
          <p>Credits are applied to future invoices when uptime falls below committed levels according to policy bands.</p>
        </section>
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">4. Exclusions</h2>
          <p>Planned maintenance, force majeure, and customer-caused outages are excluded from SLA calculations.</p>
        </section>
      </div>
    </div>
  )
}
