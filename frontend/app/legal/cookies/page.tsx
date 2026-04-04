export default function CookiesPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="mb-2 text-3xl font-semibold text-foreground">Cookie Policy</h1>
      <p className="mb-10 text-sm text-muted-foreground">Last updated: March 2026</p>
      <div className="space-y-8 text-foreground">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-foreground">Cookies We Use</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-foreground">
                  <th className="py-2 text-left">Cookie</th>
                  <th className="py-2 text-left">Purpose</th>
                  <th className="py-2 text-left">Duration</th>
                  <th className="py-2 text-left">Essential</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr>
                  <td className="py-3 font-mono text-xs">next-auth.session-token</td>
                  <td className="py-3">Authentication session</td>
                  <td className="py-3">7 days</td>
                  <td className="py-3 text-[hsl(var(--brand-success))]">Yes</td>
                </tr>
                <tr>
                  <td className="py-3 font-mono text-xs">next-auth.csrf-token</td>
                  <td className="py-3">CSRF protection</td>
                  <td className="py-3">Session</td>
                  <td className="py-3 text-[hsl(var(--brand-success))]">Yes</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-muted-foreground">
            We use only essential cookies. We do not use advertising, analytics, or tracking cookies.
          </p>
        </section>
      </div>
    </div>
  )
}
