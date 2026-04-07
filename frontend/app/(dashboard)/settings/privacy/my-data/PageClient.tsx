"use client"

import { useState } from "react"
import { exportOwnData } from "@/lib/api/compliance"
import { DataExportRequest } from "@/components/settings/DataExportRequest"

type ExportHistoryRow = {
  requestId: string
  requestedAt: string
}

export default function PrivacyMyDataPage() {
  const [history, setHistory] = useState<ExportHistoryRow[]>([])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">My Data Export</h1>
        <p className="text-sm text-muted-foreground">Request a portability export of your personal data.</p>
      </header>

      <DataExportRequest
        onRequest={async () => {
          const payload = await exportOwnData()
          const requestIdRaw = payload.request_id
          const requestId = typeof requestIdRaw === "string" ? requestIdRaw : "-"
          setHistory((current) => [
            {
              requestId,
              requestedAt: new Date().toISOString(),
            },
            ...current,
          ])
          return payload
        }}
      />

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Past Export Requests</h2>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">No export requests yet.</p>
        ) : (
          <ul className="space-y-2 text-sm text-muted-foreground">
            {history.map((row) => (
              <li key={`${row.requestId}-${row.requestedAt}`}>
                {row.requestId} — {row.requestedAt}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

