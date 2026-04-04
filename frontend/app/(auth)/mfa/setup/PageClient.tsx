"use client"

import * as React from "react"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { useState } from "react"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui/FormField"

type Step = "generate" | "verify" | "done"

function MaskedSecret({ secret }: { secret: string }) {
  const [revealed, setRevealed] = React.useState(false)

  return (
    <div className="relative">
      <code
        aria-label={revealed ? "MFA secret key" : "MFA secret key, hidden"}
        className="block break-all rounded-md bg-muted px-3 py-2 font-mono text-sm select-all"
      >
        {revealed ? secret : "\u2022".repeat(secret.length)}
      </code>
      <button
        type="button"
        onClick={() => setRevealed((value) => !value)}
        className="mt-1 text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
        aria-pressed={revealed}
      >
        {revealed ? "Hide secret key" : "Reveal secret key"}
      </button>
    </div>
  )
}

export default function MFASetupPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>("generate")
  const [secret, setSecret] = useState("")
  const [qrUrl, setQrUrl] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ code?: string }>({})
  const [loading, setLoading] = useState(false)
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [recoveryCodesRevealed, setRecoveryCodesRevealed] = useState(false)
  const [copiedRecoveryCodes, setCopiedRecoveryCodes] = useState(false)

  const authHeaders = (): Record<string, string> => {
    const setupToken = sessionStorage.getItem("mfa_setup_token")
    if (!setupToken) return {}
    return { Authorization: `Bearer ${setupToken}` }
  }

  const generateSecret = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    try {
      const payload = await apiClient.post<{ secret?: string; qr_url?: string }>(
        "/api/v1/auth/mfa/setup",
        {},
        { headers: authHeaders() },
      )
      setSecret(payload.data?.secret ?? "")
      setQrUrl(payload.data?.qr_url ?? "")
      setStep("verify")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to initialise MFA setup")
    } finally {
      setLoading(false)
    }
  }

  const verifyAndEnable = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    setFieldErrors({})
    if (code.length !== 6) {
      setFieldErrors({ code: "Enter the 6-digit code from your authenticator app" })
      setLoading(false)
      return
    }
    try {
      const payload = await apiClient.post<{ access_token?: string; refresh_token?: string; recovery_codes?: string[] }>(
        "/api/v1/auth/mfa/verify-setup",
        { code, secret },
        {
          headers: {
            ...authHeaders(),
          },
        },
      )
      setRecoveryCodes(payload.data?.recovery_codes ?? [])
      sessionStorage.removeItem("mfa_setup_token")
      setStep("done")
      setTimeout(() => router.push("/login?registered=true"), 2000)
    } catch {
      setFieldErrors({ code: "Invalid code. Check your authenticator app and try again." })
    } finally {
      setLoading(false)
    }
  }

  const copyRecoveryCodes = async (): Promise<void> => {
    if (!recoveryCodes.length) {
      return
    }

    try {
      await navigator.clipboard.writeText(recoveryCodes.join("\n"))
      setCopiedRecoveryCodes(true)
      window.setTimeout(() => setCopiedRecoveryCodes(false), 2000)
    } catch {
      setCopiedRecoveryCodes(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-4 text-center">
        <h2 className="text-xl font-semibold text-foreground">Set Up Two-Factor Authentication</h2>
        <p className="mt-1 text-sm text-muted-foreground">Required to access FinanceOps.</p>
      </div>
      {step === "generate" ? (
        <button onClick={generateSecret} disabled={loading} className="w-full rounded-md bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Generating..." : "Begin MFA Setup"}
        </button>
      ) : null}
      {step === "verify" ? (
        <div className="space-y-3">
          <div className="flex justify-center rounded-md bg-white p-3">
            <Image
              src={qrUrl}
              alt="QR code for MFA setup"
              width={192}
              height={192}
              unoptimized
              className="h-48 w-48"
            />
          </div>
          <div className="space-y-2">
            <p className="text-center text-xs text-gray-400">Manual key</p>
            <MaskedSecret secret={secret} />
          </div>
          <FormField
            id="otp-code"
            label="Verification code"
            error={fieldErrors.code}
            hint="Enter the 6-digit code from your authenticator app"
            required
          >
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
              autoComplete="one-time-code"
              inputMode="numeric"
              pattern="[0-9]*"
              className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-center font-mono text-white"
            />
          </FormField>
          {error ? <p className="text-sm text-red-400">{error}</p> : null}
          <button onClick={verifyAndEnable} disabled={loading || code.length !== 6} className="w-full rounded-md bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
            {loading ? "Verifying..." : "Verify & Enable MFA"}
          </button>
        </div>
      ) : null}
      {step === "done" ? (
        <div className="space-y-3 text-center">
          <p className="text-green-400">MFA enabled successfully</p>
          {recoveryCodes.length ? (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-left">
              <p className="mb-2 text-xs text-amber-300">Save these one-time recovery codes now:</p>
              <div className="space-y-2" aria-live="polite">
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setRecoveryCodesRevealed((value) => !value)}
                    className="text-xs text-amber-100 underline underline-offset-2 hover:text-white"
                    aria-pressed={recoveryCodesRevealed}
                  >
                    {recoveryCodesRevealed ? "Hide recovery codes" : "Reveal recovery codes"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void copyRecoveryCodes()}
                    className="text-xs text-amber-100 underline underline-offset-2 hover:text-white"
                    aria-label="Copy all recovery codes"
                  >
                    Copy all recovery codes
                  </button>
                  {copiedRecoveryCodes ? (
                    <span className="text-xs text-amber-100">Copied</span>
                  ) : null}
                </div>
                {recoveryCodesRevealed ? (
                  <ul className="space-y-1 font-mono text-xs text-amber-100">
                    {recoveryCodes.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <div
                    aria-label="Recovery codes hidden"
                    className="space-y-1 font-mono text-xs text-amber-100"
                  >
                    {recoveryCodes.map((item) => (
                      <div key={item}>{"\u2022".repeat(item.length)}</div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null}
          <p className="text-sm text-gray-400">Redirecting to sign in...</p>
        </div>
      ) : null}
    </div>
  )
}
