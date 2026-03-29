"use client"

import { useState } from "react"

interface DataExportRequestProps {
  onRequest: () => Promise<Record<string, unknown>>
}

export function DataExportRequest({ onRequest }: DataExportRequestProps) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const requestExport = async () => {
    setLoading(true)
    try {
      const payload = await onRequest()
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = "gdpr_export.json"
      anchor.click()
      URL.revokeObjectURL(url)
      setMessage("Data export generated and downloaded.")
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to request export")
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-lg font-semibold text-foreground">Request My Data Export</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        The export includes your profile, claims, checklist tasks, compliance events, consent records, and erasure history.
      </p>
      <button
        type="button"
        onClick={() => void requestExport()}
        disabled={loading}
        className="mt-3 rounded-md border border-border px-3 py-2 text-sm text-foreground"
      >
        {loading ? "Requesting..." : "Request My Data Export"}
      </button>
      {message ? <p className="mt-2 text-xs text-muted-foreground">{message}</p> : null}
    </section>
  )
}

