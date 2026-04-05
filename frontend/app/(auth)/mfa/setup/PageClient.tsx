"use client"

import * as React from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import { signIn } from "next-auth/react"
import QRCode from "react-qr-code"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Dialog } from "@/components/ui/Dialog"
import { navigateAfterAuth, waitForEstablishedSession } from "@/lib/auth-handoff"
import { getSafeCallbackUrl } from "@/lib/login-flow"
import { useTenantStore } from "@/lib/store/tenant"

type Step = "generate" | "verify" | "done"
type SessionTokens = {
  access_token: string
  refresh_token: string
}

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
  const searchParams = useSearchParams()
  const setTenant = useTenantStore((state) => state.setTenant)
  const callbackUrl = getSafeCallbackUrl(searchParams?.get("callbackUrl"))
  const [step, setStep] = useState<Step>("generate")
  const [secret, setSecret] = useState("")
  const [otpauthUri, setOtpauthUri] = useState("")
  const [code, setCode] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ code?: string }>({})
  const [loading, setLoading] = useState(false)
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [recoveryCodesRevealed, setRecoveryCodesRevealed] = useState(false)
  const [copiedRecoveryCodes, setCopiedRecoveryCodes] = useState(false)
  const [recoveryDialogOpen, setRecoveryDialogOpen] = useState(false)
  const [recoveryCodesSaved, setRecoveryCodesSaved] = useState(false)
  const [sessionTokens, setSessionTokens] = useState<SessionTokens | null>(null)

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
      const nextSecret = (payload.data?.secret ?? "").replace(/\s+/g, "").toUpperCase()
      const nextOtpauthUri = (payload.data?.qr_url ?? "").trim()
      if (!nextSecret || !nextOtpauthUri) {
        throw new Error("MFA setup payload was incomplete")
      }
      setSecret(nextSecret)
      setOtpauthUri(nextOtpauthUri)
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
        { code },
        {
          headers: {
            ...authHeaders(),
          },
        },
      )
      const accessToken = payload.data?.access_token
      const refreshToken = payload.data?.refresh_token
      if (!accessToken || !refreshToken) {
        setError("MFA setup succeeded but session tokens were not returned. Please try signing in again.")
        return
      }
      setSessionTokens({
        access_token: accessToken,
        refresh_token: refreshToken,
      })
      setRecoveryCodes(payload.data?.recovery_codes ?? [])
      setRecoveryCodesSaved(false)
      setRecoveryDialogOpen(true)
      sessionStorage.removeItem("mfa_setup_token")
      setStep("done")
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

  const continueToDashboard = async (): Promise<void> => {
    if (!recoveryCodesSaved) {
      return
    }
    if (!sessionTokens) {
      setError("Session data missing. Please sign in again.")
      return
    }

    setLoading(true)
    try {
      const result = await signIn("credentials", {
        redirect: false,
        access_token: sessionTokens.access_token,
        refresh_token: sessionTokens.refresh_token,
      })
      if (!result || result.ok !== true || result.error) {
        setError("Unable to establish session. Please sign in again.")
        return
      }

      const session = await waitForEstablishedSession()
      const user = session?.user
      if (user?.tenant_id && user.tenant_slug) {
        setTenant({
          tenant_id: user.tenant_id,
          tenant_slug: user.tenant_slug,
          org_setup_complete: user.org_setup_complete,
          org_setup_step: user.org_setup_step,
          entity_roles: user.entity_roles,
          active_entity_id: user.entity_roles.at(0)?.entity_id ?? null,
        })
      }

      setRecoveryDialogOpen(false)
      setRecoveryCodes([])
      setSessionTokens(null)
      navigateAfterAuth(callbackUrl)
    } finally {
      setLoading(false)
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
            {otpauthUri ? (
              <QRCode
                value={otpauthUri}
                size={192}
                bgColor="#FFFFFF"
                fgColor="#111827"
                level="M"
                className="h-48 w-48"
              />
            ) : (
              <div className="flex h-48 w-48 items-center justify-center text-center text-sm text-muted-foreground">
                QR code unavailable. Use the manual key below.
              </div>
            )}
          </div>
          <div className="space-y-2">
            <p className="text-center text-xs text-gray-400">Manual key</p>
            <MaskedSecret secret={secret} />
            <p className="text-center text-xs text-muted-foreground">
              Enter this exact base32 key in your authenticator app with no extra spaces.
            </p>
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
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
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
          <p className="text-sm text-gray-400">Complete recovery code acknowledgement to continue.</p>
        </div>
      ) : null}

      <Dialog
        open={recoveryDialogOpen}
        onClose={() => {}}
        title="Save your recovery codes"
        description="These one-time codes can be used to access your account if you lose your authenticator app."
        size="md"
      >
        <div className="space-y-4">
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-left">
            <p className="mb-2 text-xs text-amber-300">Store these codes in a secure location:</p>
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
                  Copy all
                </button>
                {copiedRecoveryCodes ? (
                  <span className="text-xs text-amber-100">Copied</span>
                ) : null}
              </div>
              {recoveryCodes.length ? (
                recoveryCodesRevealed ? (
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
                )
              ) : (
                <p className="text-xs text-amber-100">
                  Recovery codes were not returned. Continue only after confirming backup access with your admin.
                </p>
              )}
            </div>
          </div>

          <label className="flex items-start gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              className="mt-1"
              checked={recoveryCodesSaved}
              onChange={(event) => setRecoveryCodesSaved(event.target.checked)}
            />
            <span>I have saved my recovery codes</span>
          </label>

          <Button
            type="button"
            className="w-full"
            disabled={!recoveryCodesSaved || loading}
            onClick={() => void continueToDashboard()}
          >
            {loading ? "Finishing sign-in..." : "Continue to Dashboard"}
          </Button>
        </div>
      </Dialog>
    </div>
  )
}
