"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import apiClient from "@/lib/api/client"
import { FormField } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

type CompanyType = "ca_firm" | "corporate" | "other"

interface RegisterForm {
  fullName: string
  email: string
  password: string
  confirmPassword: string
  companyName: string
  companyType: CompanyType
  phone: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm] = useState<RegisterForm>({
    fullName: "",
    email: "",
    password: "",
    confirmPassword: "",
    companyName: "",
    companyType: "corporate",
    phone: "",
  })
  const [errors, setErrors] = useState<Partial<Record<keyof RegisterForm, string>>>({})
  const [loading, setLoading] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [termsAccepted, setTermsAccepted] = useState(false)

  const validate = (): boolean => {
    const nextErrors: Partial<Record<keyof RegisterForm, string>> = {}
    if (!form.fullName.trim()) nextErrors.fullName = "Full name is required"
    if (!form.email.includes("@")) nextErrors.email = "Valid email required"
    if (form.password.length < 8) nextErrors.password = "Minimum 8 characters"
    if (form.password !== form.confirmPassword) nextErrors.confirmPassword = "Passwords do not match"
    if (!form.companyName.trim()) nextErrors.companyName = "Company name is required"
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const submit = async (): Promise<void> => {
    if (!validate()) return
    if (!termsAccepted) {
      setServerError("You must accept the Terms of Service to continue")
      return
    }
    setLoading(true)
    setServerError(null)
    try {
      const tenantType = form.companyType === "ca_firm" ? "ca_firm" : "direct"
      const payload = await apiClient.post<{ status?: string; setup_token?: string }>(
        "/api/v1/auth/register",
        {
          full_name: form.fullName,
          email: form.email,
          password: form.password,
          tenant_name: form.companyName,
          tenant_type: tenantType,
          country: "IN",
          terms_accepted: termsAccepted,
        },
      )
      if (payload.data?.status === "requires_mfa_setup" && payload.data.setup_token) {
        sessionStorage.setItem("mfa_setup_token", payload.data.setup_token)
        router.push("/mfa/setup")
        return
      }
      router.push("/login?registered=true")
    } catch (error) {
      setServerError(error instanceof Error ? error.message : "Registration failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-4 space-y-1 text-center">
        <h2 className="text-xl font-semibold text-foreground">Create your FinanceOps account</h2>
        <p className="text-sm text-muted-foreground">Enterprise finance platform for CA firms and corporates</p>
      </div>
      <div className="space-y-4">
        <FormField id="register-full-name" error={errors.fullName} label="Full Name" required>
          <Input placeholder="Full Name" value={form.fullName} onChange={(e) => setForm((f) => ({ ...f, fullName: e.target.value }))} />
        </FormField>
        <FormField id="register-email" error={errors.email} label="Work Email" required>
          <Input type="email" placeholder="Work Email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
        </FormField>
        <FormField id="register-company-name" error={errors.companyName} label="Company / Firm Name" required>
          <Input placeholder="Company / Firm Name" value={form.companyName} onChange={(e) => setForm((f) => ({ ...f, companyName: e.target.value }))} />
        </FormField>
        <FormField id="register-company-type" label="Company Type" required>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            value={form.companyType}
            onChange={(e) => setForm((f) => ({ ...f, companyType: e.target.value as CompanyType }))}
          >
            <option value="ca_firm">CA / Accounting Firm</option>
            <option value="corporate">Corporate / Company</option>
            <option value="other">Other</option>
          </select>
        </FormField>
        <FormField id="register-password" error={errors.password} label="Password" required>
          <Input type="password" placeholder="Password (min 8 chars)" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
        </FormField>
        <FormField id="register-confirm-password" error={errors.confirmPassword} label="Confirm Password" required>
          <Input type="password" placeholder="Confirm Password" value={form.confirmPassword} onChange={(e) => setForm((f) => ({ ...f, confirmPassword: e.target.value }))} />
        </FormField>
        <div className="flex items-start gap-3">
          <input
            id="terms"
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => setTermsAccepted(e.target.checked)}
            className="mt-1 rounded border-border bg-background text-[hsl(var(--brand-primary))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
          <label htmlFor="terms" className="text-sm text-muted-foreground">
            I agree to the{" "}
            <a href="/legal/terms" target="_blank" className="text-foreground transition hover:text-muted-foreground" rel="noreferrer">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/legal/privacy" target="_blank" className="text-foreground transition hover:text-muted-foreground" rel="noreferrer">
              Privacy Policy
            </a>
          </label>
        </div>
        {serverError ? <p className="text-sm text-[hsl(var(--brand-danger))]">{serverError}</p> : null}
        <Button className="w-full" disabled={loading} onClick={submit} type="button">
          {loading ? "Creating account..." : "Create Account"}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="text-foreground transition hover:text-muted-foreground">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
