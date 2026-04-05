"use client"

import { Suspense, useState } from "react"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { getSession, signIn } from "next-auth/react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import apiClient, { BASE_URL } from "@/lib/api/client"
import {
  getSafeCallbackUrl,
  isLoginTokenPayload,
  type BackendLoginPayload,
} from "@/lib/login-flow"
import { useTenantStore } from "@/lib/store/tenant"

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
})

type LoginFormValues = z.infer<typeof loginSchema>
const BACKEND_LOGIN_TIMEOUT_MS = 8000

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  )
}

function LoginPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setTenant = useTenantStore((state) => state.setTenant)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const registered = searchParams?.get("registered")
  const reset = searchParams?.get("reset")
  const callbackUrl = getSafeCallbackUrl(searchParams?.get("callbackUrl"))

  const { register, handleSubmit, formState } = useForm<LoginFormValues>({
    defaultValues: {
      email: "",
      password: "",
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null)
    const parsed = loginSchema.safeParse(values)
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid login payload")
      return
    }

    setIsSubmitting(true)
    try {
      if (!BASE_URL) {
        setFormError("Application configuration error: missing NEXT_PUBLIC_API_URL")
        return
      }

      const controller = new AbortController()
      const timeoutId = window.setTimeout(() => controller.abort(), BACKEND_LOGIN_TIMEOUT_MS)

      try {
        const loginResponse = await apiClient.post<BackendLoginPayload>(
          "/api/v1/auth/login",
          {
            email: parsed.data.email,
            password: parsed.data.password,
          },
          {
            signal: controller.signal,
            timeout: BACKEND_LOGIN_TIMEOUT_MS,
          },
        )
        const loginData = loginResponse.data

        if (
          "requires_password_change" in loginData &&
          loginData.requires_password_change
        ) {
          sessionStorage.setItem("password_change_token", loginData.password_change_token)
          router.push(`/auth/change-password?callbackUrl=${encodeURIComponent(callbackUrl)}`)
          return
        }

        if (
          "requires_mfa_setup" in loginData &&
          loginData.requires_mfa_setup
        ) {
          sessionStorage.setItem("mfa_setup_token", loginData.setup_token)
          router.push(`/mfa/setup?callbackUrl=${encodeURIComponent(callbackUrl)}`)
          return
        }

        if ("requires_mfa" in loginData && loginData.requires_mfa) {
          const mfaUrl = new URL("/mfa", window.location.origin)
          mfaUrl.searchParams.set("challenge", loginData.mfa_challenge_token)
          mfaUrl.searchParams.set("callbackUrl", callbackUrl)
          router.push(`${mfaUrl.pathname}${mfaUrl.search}`)
          return
        }

        if (!isLoginTokenPayload(loginData)) {
          setFormError("Unable to complete sign-in. Please try again.")
          return
        }

        const signInResult = await signIn("credentials", {
          redirect: false,
          access_token: loginData.access_token,
          refresh_token: loginData.refresh_token,
        })

        if (!signInResult || signInResult.ok !== true || signInResult.error) {
          setFormError("Unable to establish session. Please try again.")
          return
        }

        const session = await getSession()
        const user = session?.user
        if (!user?.tenant_id || !user.tenant_slug) {
          setFormError("Sign-in completed but user context is missing. Please try again.")
          return
        }

        setTenant({
          tenant_id: user.tenant_id,
          tenant_slug: user.tenant_slug,
          org_setup_complete: user.org_setup_complete,
          org_setup_step: user.org_setup_step,
          entity_roles: user.entity_roles,
          active_entity_id: user.entity_roles.at(0)?.entity_id ?? null,
        })
        router.push(callbackUrl)
      } catch (error) {
        const message = error instanceof Error ? error.message.toLowerCase() : ""
        if (message.includes("invalid email or password")) {
          setFormError("Invalid email or password")
          return
        }
        if (message.includes("aborted")) {
          setFormError("Sign-in timed out. Please try again.")
          return
        }
        setFormError("Unable to sign in right now. Please try again.")
      } finally {
        window.clearTimeout(timeoutId)
      }
    } finally {
      setIsSubmitting(false)
    }
  })

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 space-y-1">
        <h2 className="text-xl font-semibold text-foreground">
          Sign in to FinanceOps
        </h2>
        <p className="text-sm text-muted-foreground">
          Use your admin-provisioned account credentials.
        </p>
      </div>
      <form className="space-y-4" onSubmit={onSubmit}>
        {registered ? (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
            <p className="text-sm text-green-400">Account created successfully. Please sign in.</p>
          </div>
        ) : null}
        {reset ? (
          <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
            <p className="text-sm text-green-400">Password reset successful. Please sign in.</p>
          </div>
        ) : null}
        <FormField
          id="email"
          label="Email address"
          error={formState.errors.email?.message}
          required
        >
          <Input
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            {...register("email")}
          />
        </FormField>
        <FormField
          id="password"
          label="Password"
          error={formState.errors.password?.message}
          required
        >
          <Input
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            {...register("password")}
          />
        </FormField>
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-sm text-gray-400 hover:text-blue-400">
            Forgot password?
          </Link>
        </div>
        {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
        <Button className="h-10 w-full" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </Button>
        <p className="mt-4 text-center text-sm text-gray-400">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-blue-400 hover:text-blue-300">
            Create one free
          </Link>
        </p>
      </form>
    </div>
  )
}
