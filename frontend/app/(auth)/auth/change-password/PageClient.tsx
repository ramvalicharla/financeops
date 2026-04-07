"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useState } from "react"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getSafeCallbackUrl } from "@/lib/login-flow"

const PASSWORD_POLICY_HINT =
  "Minimum 8 characters, including 1 uppercase letter, 1 number, and 1 special character."

const validatePassword = (value: string): string | null => {
  if (value.length < 8) return "Password must be at least 8 characters"
  if (!/[A-Z]/.test(value)) return "Password must include at least 1 uppercase letter"
  if (!/[0-9]/.test(value)) return "Password must include at least 1 number"
  if (!/[^A-Za-z0-9]/.test(value)) return "Password must include at least 1 special character"
  return null
}

type ChangePasswordResponse =
  | { status: "requires_mfa_setup"; requires_mfa_setup: true; setup_token: string }
  | { status: "password_changed" }

export default function ChangePasswordPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const callbackUrl = getSafeCallbackUrl(searchParams?.get("callbackUrl"))
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    password?: string
    confirmPassword?: string
  }>({})
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (): Promise<void> => {
    setError(null)
    setFieldErrors({})

    const token = sessionStorage.getItem("password_change_token")
    if (!token) {
      setError("Password change token missing. Sign in again.")
      return
    }

    const passwordError = validatePassword(password)
    if (passwordError) {
      setFieldErrors({ password: passwordError })
      return
    }
    if (password !== confirmPassword) {
      setFieldErrors({ confirmPassword: "Passwords do not match" })
      return
    }

    setLoading(true)
    try {
      const response = await apiClient.post<ChangePasswordResponse>(
        "/api/v1/auth/change-password",
        { new_password: password },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      sessionStorage.removeItem("password_change_token")

      if (
        response.data &&
        "requires_mfa_setup" in response.data &&
        response.data.requires_mfa_setup
      ) {
        sessionStorage.setItem("mfa_setup_token", response.data.setup_token)
        router.push(`/mfa/setup?callbackUrl=${encodeURIComponent(callbackUrl)}`)
        return
      }

      router.push(`/login?reset=true&callbackUrl=${encodeURIComponent(callbackUrl)}`)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update password")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <h2 className="mb-4 text-center text-xl font-semibold text-foreground">
        Change your password
      </h2>
      <p className="mb-4 text-sm text-muted-foreground">{PASSWORD_POLICY_HINT}</p>
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
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter new password"
          />
        </FormField>
        <FormField
          id="confirm-password"
          label="Confirm new password"
          error={fieldErrors.confirmPassword}
          required
        >
          <Input
            autoComplete="new-password"
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Confirm new password"
          />
        </FormField>
        {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
        <Button className="w-full" disabled={loading} onClick={handleSubmit} type="button">
          {loading ? "Updating..." : "Update Password"}
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
