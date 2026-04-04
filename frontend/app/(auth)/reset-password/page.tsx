"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useState } from "react"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

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
  const [fieldErrors, setFieldErrors] = useState<{
    password?: string
    confirmPassword?: string
  }>({})
  const [loading, setLoading] = useState(false)

  const reset = async (): Promise<void> => {
    setFieldErrors({})
    if (!token) {
      setError("Invalid reset link")
      return
    }
    if (password.length < 8) {
      setError(null)
      setFieldErrors({ password: "Password must be at least 8 characters" })
      return
    }
    if (password !== confirm) {
      setError(null)
      setFieldErrors({ confirmPassword: "Passwords do not match" })
      return
    }
    setLoading(true)
    setError(null)
    try {
      await apiClient.post("/api/v1/auth/reset-password", { token, new_password: password })
      router.push("/login?reset=true")
      return
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Reset failed. Link may have expired.")
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 text-center text-xl font-semibold text-foreground">Set new password</h2>
      <div className="space-y-4">
        <FormField
          id="new-password"
          label="New password"
          error={fieldErrors.password}
          required
        >
          <Input
            autoComplete="new-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="New password (min 8 chars)"
          />
        </FormField>
        <FormField
          id="confirm-new-password"
          label="Confirm new password"
          error={fieldErrors.confirmPassword}
          required
        >
          <Input
            autoComplete="new-password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Confirm new password"
          />
        </FormField>
        {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
        <Button className="w-full" disabled={loading} onClick={reset} type="button">
          {loading ? "Resetting..." : "Reset Password"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          <Link href="/login" className="text-foreground transition hover:text-muted-foreground">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
