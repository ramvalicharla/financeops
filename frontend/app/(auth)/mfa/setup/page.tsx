"use client"

import { useRouter } from "next/navigation"
import { useState } from "react"

type Step = "generate" | "verify" | "done"

export default function MFASetupPage() {
  const router = useRouter()
  const [step, setStep] = useState<Step>("generate")
  const [secret, setSecret] = useState("")
  const [qrUrl, setQrUrl] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])

  const authHeaders = (): HeadersInit => {
    const setupToken = sessionStorage.getItem("mfa_setup_token")
    if (!setupToken) return {}
    return { Authorization: `Bearer ${setupToken}` }
  }

  const generateSecret = async (): Promise<void> => {
    setLoading(true)
    const response = await fetch("/api/v1/auth/mfa/setup", {
      method: "POST",
      headers: authHeaders(),
    })
    const payload = (await response.json()) as { data?: { secret?: string; qr_url?: string } }
    setSecret(payload.data?.secret ?? "")
    setQrUrl(payload.data?.qr_url ?? "")
    setStep("verify")
    setLoading(false)
  }

  const verifyAndEnable = async (): Promise<void> => {
    setLoading(true)
    setError(null)
    const response = await fetch("/api/v1/auth/mfa/verify-setup", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ code, secret }),
    })
    const payload = (await response.json()) as { data?: { access_token?: string; refresh_token?: string; recovery_codes?: string[] } }
    if (!response.ok) {
      setError("Invalid code. Check your authenticator app and try again.")
      setLoading(false)
      return
    }
    setRecoveryCodes(payload.data?.recovery_codes ?? [])
    sessionStorage.removeItem("mfa_setup_token")
    setStep("done")
    setLoading(false)
    setTimeout(() => router.push("/login?registered=true"), 2000)
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
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={qrUrl} alt="MFA QR Code" className="h-48 w-48" />
          </div>
          <p className="text-center text-xs text-gray-400">
            Manual key: <span className="font-mono text-gray-200">{secret}</span>
          </p>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={6}
            placeholder="6-digit code"
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-center font-mono text-white"
          />
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
              <ul className="space-y-1 font-mono text-xs text-amber-100">
                {recoveryCodes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="text-sm text-gray-400">Redirecting to sign in...</p>
        </div>
      ) : null}
    </div>
  )
}

