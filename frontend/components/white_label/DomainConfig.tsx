"use client"

import { useState } from "react"
import {
  checkWhiteLabelDomainVerification,
  initiateWhiteLabelDomainVerification,
} from "@/lib/api/white-label"

interface DomainConfigProps {
  currentDomain: string
  verified: boolean
  readOnly?: boolean
}

export function DomainConfig({ currentDomain, verified, readOnly = false }: DomainConfigProps) {
  const [domain, setDomain] = useState(currentDomain)
  const [status, setStatus] = useState(verified)
  const [instruction, setInstruction] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const startVerification = async () => {
    setError(null)
    try {
      const payload = await initiateWhiteLabelDomainVerification(domain)
      setInstruction(`${payload.txt_record_name} = ${payload.txt_record_value}`)
      setStatus(false)
    } catch (verifyError) {
      setError(verifyError instanceof Error ? verifyError.message : "Failed to initiate verification")
    }
  }

  const checkVerification = async () => {
    setError(null)
    try {
      const payload = await checkWhiteLabelDomainVerification()
      setStatus(payload.verified)
    } catch (verifyError) {
      setError(verifyError instanceof Error ? verifyError.message : "Failed to check verification")
    }
  }

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-foreground">Domain Configuration</h3>
      <label className="text-xs text-muted-foreground">
        Custom Domain
        <input
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          disabled={readOnly}
          className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          placeholder="finance.example.com"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full border border-border px-2 py-0.5 text-muted-foreground">
          {status ? "Verified" : "Pending verification"}
        </span>
        <button
          type="button"
          onClick={() => void startVerification()}
          disabled={readOnly}
          className="rounded-md border border-border px-3 py-1.5 text-foreground"
        >
          Change Domain
        </button>
        <button
          type="button"
          onClick={() => void checkVerification()}
          disabled={readOnly}
          className="rounded-md border border-border px-3 py-1.5 text-foreground"
        >
          Check Verification
        </button>
      </div>
      {instruction ? (
        <p className="rounded-md border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
          Add TXT record: {instruction}
        </p>
      ) : null}
      {error ? <p className="text-xs text-[hsl(var(--brand-danger))]">{error}</p> : null}
    </section>
  )
}
