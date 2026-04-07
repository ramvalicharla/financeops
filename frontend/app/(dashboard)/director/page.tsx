import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Director")

export default function DirectorDashboardPage() {
  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-semibold text-white">Director Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <h2 className="text-sm font-semibold text-amber-300">Pending Signoffs</h2>
          <p className="mt-1 text-sm text-gray-300">Review and sign pending board documents.</p>
        </div>
        <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 p-4">
          <h2 className="text-sm font-semibold text-blue-300">Board Packs Awaiting Review</h2>
          <p className="mt-1 text-sm text-gray-300">Open latest packs and review commentary.</p>
        </div>
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
          <h2 className="text-sm font-semibold text-red-300">Covenant Status Summary</h2>
          <p className="mt-1 text-sm text-gray-300">Track breached and near-breach facilities.</p>
        </div>
        <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
          <h2 className="text-sm font-semibold text-gray-100">Key Financial KPIs (Read-only)</h2>
          <p className="mt-1 text-sm text-gray-300">Revenue, EBITDA, cash position, and run-rate trends.</p>
        </div>
      </div>
    </div>
  )
}

