export default function CookiesPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-16">
      <h1 className="mb-2 text-3xl font-bold text-white">Cookie Policy</h1>
      <p className="mb-10 text-sm text-gray-400">Last updated: March 2026</p>
      <div className="space-y-8 text-gray-300">
        <section>
          <h2 className="mb-3 text-xl font-semibold text-white">Cookies We Use</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-white">
                  <th className="py-2 text-left">Cookie</th>
                  <th className="py-2 text-left">Purpose</th>
                  <th className="py-2 text-left">Duration</th>
                  <th className="py-2 text-left">Essential</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                <tr>
                  <td className="py-3 font-mono text-xs">next-auth.session-token</td>
                  <td className="py-3">Authentication session</td>
                  <td className="py-3">7 days</td>
                  <td className="py-3 text-green-400">Yes</td>
                </tr>
                <tr>
                  <td className="py-3 font-mono text-xs">next-auth.csrf-token</td>
                  <td className="py-3">CSRF protection</td>
                  <td className="py-3">Session</td>
                  <td className="py-3 text-green-400">Yes</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm text-gray-400">
            We use only essential cookies. We do not use advertising, analytics, or tracking cookies.
          </p>
        </section>
      </div>
    </div>
  )
}

