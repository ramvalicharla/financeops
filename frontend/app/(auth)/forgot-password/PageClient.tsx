"use client"

import Link from "next/link"
import { useState } from "react"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async (): Promise<void> => {
    if (!email.includes("@")) return
    setLoading(true)
    try {
      await apiClient.post("/api/v1/auth/forgot-password", { email })
      setSubmitted(true)
    } catch {
      setSubmitted(true)
    }
    setLoading(false)
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 text-center">
        <h2 className="text-xl font-semibold text-foreground">Reset your password</h2>
        <p className="mt-1 text-sm text-muted-foreground">Enter your email and we&apos;ll send a reset link</p>
      </div>
      {!submitted ? (
        <div className="space-y-4">
          <FormField id="forgot-password-email" label="Email" required>
            <Input
              autoComplete="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </FormField>
          <Button className="w-full" disabled={loading} onClick={submit} type="button">
            {loading ? "Sending..." : "Send Reset Link"}
          </Button>
        </div>
      ) : (
        <div className="space-y-2 text-center">
          <p className="text-foreground">Check your inbox</p>
          <p className="text-sm text-muted-foreground">If an account exists for {email}, you&apos;ll receive a reset link shortly.</p>
        </div>
      )}
      <p className="mt-4 text-center text-sm text-muted-foreground">
        <Link href="/login" className="text-foreground transition hover:text-muted-foreground">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
