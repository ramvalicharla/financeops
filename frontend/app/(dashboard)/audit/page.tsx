"use client"

import { useEffect, useState } from "react"
import { AuditorAccessPanel } from "@/components/audit/AuditorAccessPanel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  grantAuditorAccess,
  listAuditorAccess,
  revokeAuditorAccess,
} from "@/lib/api/sprint11"
import { type AuditorPortalAccess } from "@/lib/types/sprint11"

export default function AuditPage() {
  const [rows, setRows] = useState<AuditorPortalAccess[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [plainTokenMap, setPlainTokenMap] = useState<Record<string, string>>({})

  const [auditorEmail, setAuditorEmail] = useState("")
  const [auditorFirm, setAuditorFirm] = useState("")
  const [engagementName, setEngagementName] = useState("Statutory Audit")
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 10))
  const [validUntil, setValidUntil] = useState(new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10))

  const load = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listAuditorAccess({ limit: 100, offset: 0 })
      setRows(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load auditor access")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const grant = async (): Promise<void> => {
    setError(null)
    try {
      const payload = await grantAuditorAccess({
        auditor_email: auditorEmail,
        auditor_firm: auditorFirm,
        engagement_name: engagementName,
        valid_from: validFrom,
        valid_until: validUntil,
        modules_accessible: ["audit", "statutory", "tax"],
      })
      setPlainTokenMap((prev) => ({ ...prev, [payload.access.id]: payload.token }))
      await load()
    } catch (grantError) {
      setError(grantError instanceof Error ? grantError.message : "Failed to grant auditor access")
    }
  }

  const revoke = async (accessId: string): Promise<void> => {
    try {
      await revokeAuditorAccess(accessId)
      await load()
    } catch (revokeError) {
      setError(revokeError instanceof Error ? revokeError.message : "Failed to revoke access")
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-foreground">Audit Portal</h1>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold text-foreground">Grant New Access</h2>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <Input placeholder="Auditor email" value={auditorEmail} onChange={(event) => setAuditorEmail(event.target.value)} />
          <Input placeholder="Auditor firm" value={auditorFirm} onChange={(event) => setAuditorFirm(event.target.value)} />
          <Input placeholder="Engagement name" value={engagementName} onChange={(event) => setEngagementName(event.target.value)} />
          <Input type="date" value={validFrom} onChange={(event) => setValidFrom(event.target.value)} />
          <Input type="date" value={validUntil} onChange={(event) => setValidUntil(event.target.value)} />
        </div>
        <Button className="mt-3" variant="outline" onClick={() => void grant()}>
          Grant Auditor Access
        </Button>
      </section>

      {loading ? <p className="text-sm text-muted-foreground">Loading engagements...</p> : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <section className="grid gap-4 md:grid-cols-2">
        {rows.map((row) => (
          <AuditorAccessPanel
            key={row.id}
            access={row}
            plainToken={plainTokenMap[row.id]}
            onRevoke={() => revoke(row.id)}
          />
        ))}
      </section>
    </div>
  )
}
