"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { type SignoffRecord } from "@/lib/types/sprint11"

export type SignoffRequestProps = {
  signoff: SignoffRecord
  onSigned: (totp: string) => Promise<void>
}

export function SignoffRequest({ signoff, onSigned }: SignoffRequestProps) {
  const [totp, setTotp] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSign = async (): Promise<void> => {
    if (totp.length !== 6) {
      setError("Enter your 6-digit authenticator code")
      return
    }
    setLoading(true)
    setError(null)
    try {
      await onSigned(totp)
      setTotp("")
    } catch {
      setError("Signing failed. Check your MFA code and try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">{signoff.document_reference}</p>
          <p className="text-xs text-muted-foreground">
            {signoff.period} · {signoff.signatory_role}
          </p>
        </div>
        <span className="rounded-md border border-amber-500/40 px-2 py-0.5 text-xs text-amber-400">
          Pending
        </span>
      </div>
      <p className="mt-3 text-sm text-foreground">&quot;{signoff.declaration_text}&quot;</p>
      <p className="mt-3 rounded-md border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.12)] px-3 py-2 text-xs text-[hsl(var(--brand-danger))]">
        This action is legally binding and irreversible.
      </p>
      <div className="mt-3 flex items-center gap-2">
        <Input
          value={totp}
          onChange={(event) => setTotp(event.target.value)}
          placeholder="6-digit MFA code"
          maxLength={6}
          className="w-40 font-mono text-center"
        />
        <Button onClick={() => void handleSign()} disabled={loading} type="button">
          {loading ? "Signing..." : "Sign with MFA"}
        </Button>
      </div>
      {error ? <p className="mt-2 text-sm text-red-400">{error}</p> : null}
    </div>
  )
}
