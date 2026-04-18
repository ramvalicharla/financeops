"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { createBreach, listBreaches } from "@/lib/api/compliance"
import type { GDPRBreach } from "@/lib/types/compliance"
import { BreachForm } from "@/components/trust/BreachForm"

export default function TrustGdprBreachPage() {
  const [breaches, setBreaches] = useState<GDPRBreach[]>([])

  const load = useCallback(async () => {
    const result = await listBreaches({ limit: 100, offset: 0 })
    setBreaches(result.data)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const latestOpen = useMemo(
    () => breaches.find((row) => row.status === "open" && ["high", "critical"].includes(row.severity)),
    [breaches],
  )

  const countdown = useMemo(() => {
    if (!latestOpen) return null
    const discovered = new Date(latestOpen.discovered_at).getTime()
    const due = discovered + 72 * 3600 * 1000
    const remainingMs = due - Date.now()
    const remainingHours = Math.max(0, Math.floor(remainingMs / (3600 * 1000)))
    return `${remainingHours}h remaining`
  }, [latestOpen])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Breach Reporting</h1>
        <p className="text-sm text-muted-foreground">Report and track GDPR breaches for your tenant.</p>
      </header>

      {latestOpen ? (
        <div className="rounded-md border border-[hsl(var(--brand-warning)/0.5)] bg-[hsl(var(--brand-warning)/0.1)] px-3 py-2 text-xs text-[hsl(var(--brand-warning))]">
          Open high/critical breach DPA deadline: {countdown}
        </div>
      ) : null}

      <BreachForm
        onSubmit={async (payload) => {
          await createBreach(payload)
          await load()
        }}
      />

      <section className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="min-w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-[0.14em] text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Severity</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Affected Users</th>
              <th className="px-3 py-2">Discovered</th>
            </tr>
          </thead>
          <tbody>
            {breaches.map((row) => (
              <tr key={row.id} className="border-b border-border/50">
                <td className="px-3 py-2">{row.breach_type}</td>
                <td className="px-3 py-2">{row.severity}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2">{row.affected_user_count}</td>
                <td className="px-3 py-2">{row.discovered_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

