"use client"

import { useEffect, useState } from "react"
import { listFinanceModules, setFinanceModuleStatus, type FinanceModuleRow } from "@/lib/api/modules"

const MODULES = ["LEASE", "REVENUE", "ASSETS", "PREPAID", "ACCRUAL", "SUBSCRIPTION"] as const

export default function ModulesPage() {
  const [rows, setRows] = useState<FinanceModuleRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await listFinanceModules()
      setRows(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load modules")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const toggle = async (moduleName: string, enabled: boolean) => {
    try {
      await setFinanceModuleStatus(moduleName, enabled)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update module")
    }
  }

  return (
    <main className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Industry Modules</h1>
        <p className="text-sm text-muted-foreground">
          Enable or disable tenant-specific accounting modules. All module-generated journals stay in draft.
        </p>
      </header>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading modules...</p> : null}

      <div className="rounded-lg border border-border bg-card">
        <table className="min-w-full text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Module</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {MODULES.map((moduleName) => {
              const existing = rows.find((row) => row.module_name === moduleName)
              const enabled = existing?.status === "ENABLED"
              return (
                <tr key={moduleName} className="border-b border-border/60">
                  <td className="px-4 py-3 font-medium">{moduleName}</td>
                  <td className="px-4 py-3">{enabled ? "ENABLED" : "DISABLED"}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => void toggle(moduleName, !enabled)}
                      className="rounded-md border border-border px-3 py-1.5 hover:bg-accent"
                    >
                      {enabled ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </main>
  )
}

