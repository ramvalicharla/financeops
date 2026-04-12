"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui/FormField"

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={null}>
      <AcceptInvitePageContent />
    </Suspense>
  )
}

function AcceptInvitePageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams?.get("token") ?? null

  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    password?: string
    confirmPassword?: string
  }>({})
  const [loading, setLoading] = useState(false)

  async function handleActivate() {
    setError(null)
    setFieldErrors({})
    if (!token) {
      setError("Invalid invitation link")
      return
    }
    if (password.length < 8) {
      setFieldErrors({ password: "Password must be at least 8 characters" })
      return
    }
    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match" })
      return
    }
    if (!termsAccepted) {
      setError("You must accept the Terms of Service")
      return
    }

    setLoading(true)
    try {
      await apiClient.post("/api/v1/auth/accept-invite", {
          token,
          password,
          terms_accepted: termsAccepted,
      })
      router.push("/login?registered=true")
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Invitation activation failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 space-y-1">
        <h2 className="text-xl font-semibold text-foreground">Accept Invitation</h2>
        <p className="text-sm text-muted-foreground">
          Set your password to activate your Finqor account.
        </p>
      </div>

      <div className="space-y-4">
        <FormField
          id="password"
          label="Password"
          error={fieldErrors.password}
          required
        >
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white"
          />
        </FormField>
        <FormField
          id="confirm-password"
          label="Confirm password"
          error={fieldErrors.confirmPassword}
          required
        >
          <input
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white"
          />
        </FormField>
        <label className="flex items-start gap-3 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(event) => setTermsAccepted(event.target.checked)}
            className="mt-1"
          />
          <span>
            I agree to the <Link href="/legal/terms" className="text-blue-400">Terms</Link> and{" "}
            <Link href="/legal/privacy" className="text-blue-400">Privacy Policy</Link>.
          </span>
        </label>
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <button
          type="button"
          onClick={() => void handleActivate()}
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Activating..." : "Activate Account"}
        </button>
      </div>
    </div>
  )
}
