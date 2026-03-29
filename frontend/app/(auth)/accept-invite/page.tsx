"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.trim() ?? ""

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
  const [loading, setLoading] = useState(false)

  async function handleActivate() {
    setError(null)
    if (!token) {
      setError("Invalid invitation link")
      return
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }
    if (!termsAccepted) {
      setError("You must accept the Terms of Service")
      return
    }
    if (!API_BASE_URL) {
      setError("Application configuration error: missing NEXT_PUBLIC_API_URL")
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/accept-invite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          terms_accepted: termsAccepted,
        }),
      })
      const payload = (await response.json()) as {
        data?: { message?: string }
        error?: { message?: string }
      }
      if (!response.ok) {
        setError(payload.error?.message ?? "Invitation activation failed")
        return
      }
      router.push("/login?registered=true")
    } catch {
      setError("Network error. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 space-y-1">
        <h2 className="text-xl font-semibold text-foreground">Accept Invitation</h2>
        <p className="text-sm text-muted-foreground">
          Set your password to activate your FinanceOps account.
        </p>
      </div>

      <div className="space-y-4">
        <input
          type="password"
          placeholder="New password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white"
        />
        <input
          type="password"
          placeholder="Confirm password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-white"
        />
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
