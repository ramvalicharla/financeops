"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordPageContent />
    </Suspense>
  )
}

function ResetPasswordPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams?.get("token")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const reset = async (): Promise<void> => {
    if (!token) {
      setError("Invalid reset link")
      return
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    if (password !== confirm) {
      setError("Passwords do not match")
      return
    }
    setLoading(true)
    setError(null)
    const response = await fetch("/api/v1/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, new_password: password }),
    })
    if (response.ok) {
      router.push("/login?reset=true")
      return
    }
    const payload = (await response.json()) as { detail?: string }
    setError(payload.detail ?? "Reset failed. Link may have expired.")
    setLoading(false)
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 text-center text-xl font-semibold text-foreground">Set new password</h2>
      <div className="space-y-3">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="New password (min 8 chars)"
          className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white"
        />
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Confirm new password"
          className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white"
        />
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <button onClick={reset} disabled={loading} className="w-full rounded-md bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Resetting..." : "Reset Password"}
        </button>
      </div>
    </div>
  )
}
