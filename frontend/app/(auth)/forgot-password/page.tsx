"use client"

import Link from "next/link"
import { useState } from "react"
import apiClient from "@/lib/api/client"

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
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="w-full rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-white"
          />
          <button onClick={submit} disabled={loading} className="w-full rounded-md bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
            {loading ? "Sending..." : "Send Reset Link"}
          </button>
        </div>
      ) : (
        <div className="space-y-2 text-center">
          <p className="text-white">Check your inbox</p>
          <p className="text-sm text-gray-400">If an account exists for {email}, you&apos;ll receive a reset link shortly.</p>
        </div>
      )}
      <p className="mt-4 text-center text-sm text-gray-400">
        <Link href="/login" className="text-blue-400 hover:text-blue-300">
          Back to sign in
        </Link>
      </p>
    </div>
  )
}
