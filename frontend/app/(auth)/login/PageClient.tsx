"use client"

import { Suspense, useState } from "react"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { signIn } from "next-auth/react"
import Link from "next/link"
import { ChevronLeft } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import apiClient, { BASE_URL } from "@/lib/api/client"
import {
  getSafeCallbackUrl,
  isLoginTokenPayload,
  type BackendLoginPayload,
} from "@/lib/login-flow"
import { navigateAfterAuth, waitForEstablishedSession } from "@/lib/auth-handoff"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
})

const mfaSchema = z.object({
  code: z
    .string()
    .length(6, "Enter the 6-digit verification code")
    .regex(/^\d{6}$/, "Code must contain only digits"),
})

type LoginFormValues = z.infer<typeof loginSchema>
type MFAFormValues = z.infer<typeof mfaSchema>

const BACKEND_LOGIN_TIMEOUT_MS = 8000

// ---------------------------------------------------------------------------
// Google SSO icon (inline SVG — no extra dep)
// ---------------------------------------------------------------------------

function GoogleIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M15.545 6.558a9.42 9.42 0 0 1 .139 1.626c0 2.434-.87 4.492-2.384 5.885h.002C11.978 15.292 10.158 16 8 16A8 8 0 1 1 8 0a7.689 7.689 0 0 1 5.352 2.082l-2.284 2.284A4.347 4.347 0 0 0 8 3.166c-2.087 0-3.86 1.408-4.492 3.304a4.792 4.792 0 0 0 0 3.063h.003c.635 1.893 2.405 3.301 4.492 3.301 1.078 0 2.004-.276 2.722-.764h-.003a3.702 3.702 0 0 0 1.599-2.431H8v-3.08h7.545z"
        fill="currentColor"
      />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

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
  const { setOrgId, setEntityId } = useWorkspaceStore()
  const registered = searchParams?.get("registered")
  const reset = searchParams?.get("reset")
  const callbackUrl = getSafeCallbackUrl(searchParams?.get("callbackUrl"))

  // ---- step + fade state --------------------------------------------------

  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [visible, setVisible] = useState(true)
  const [storedEmail, setStoredEmail] = useState("")
  const [mfaChallengeToken, setMfaChallengeToken] = useState<string | null>(null)

  function goToStep(n: 1 | 2 | 3) {
    setVisible(false)
    setTimeout(() => {
      setStep(n)
      setVisible(true)
    }, 150)
  }

  // ---- login form (steps 1 + 2) -------------------------------------------

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const { register, handleSubmit, formState, getValues, setValue, setError } =
    useForm<LoginFormValues>({
      defaultValues: { email: "", password: "" },
    })

  // Step 1 — validate email format, then advance
  const onContinue = () => {
    const email = getValues("email")
    const result = z.string().email("Enter a valid email address").safeParse(email)
    if (!result.success) {
      setError("email", { message: result.error.issues[0]?.message ?? "Enter a valid email address" })
      return
    }
    setStoredEmail(email)
    setValue("email", email)
    setFormError(null)
    goToStep(2)
  }

  // Step 2 — full login submission
  const onSignIn = handleSubmit(async (values) => {
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
          setMfaChallengeToken(loginData.mfa_challenge_token)
          goToStep(3)
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

        const session = await waitForEstablishedSession()
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
        })
        setOrgId(user.tenant_id)
        setEntityId(user.entity_roles.at(0)?.entity_id ?? null)
        navigateAfterAuth(callbackUrl)
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

  // ---- MFA form (step 3) --------------------------------------------------

  const [isMfaSubmitting, setIsMfaSubmitting] = useState(false)
  const [mfaError, setMfaError] = useState<string | null>(null)

  const {
    handleSubmit: handleMfaSubmit,
    setValue: setMfaValue,
    watch: watchMfa,
  } = useForm<MFAFormValues>({ defaultValues: { code: "" } })

  const mfaCode = watchMfa("code")

  const onMfaVerify = handleMfaSubmit(async (values) => {
    if (isMfaSubmitting) return
    setMfaError(null)

    const parsed = mfaSchema.safeParse(values)
    if (!parsed.success) {
      setMfaError(parsed.error.issues[0]?.message ?? "Invalid verification code")
      return
    }
    if (!mfaChallengeToken) {
      setMfaError("MFA session expired. Please sign in again.")
      return
    }

    setIsMfaSubmitting(true)
    try {
      const verifyResponse = await apiClient.post<{
        access_token?: string
        refresh_token?: string
      }>("/api/v1/auth/mfa/verify", {
        mfa_challenge_token: mfaChallengeToken,
        totp_code: parsed.data.code,
      })

      const accessToken = verifyResponse.data?.access_token
      const refreshToken = verifyResponse.data?.refresh_token
      if (!accessToken || !refreshToken) {
        setMfaError("Unable to verify MFA right now. Please try again.")
        return
      }

      const signInResult = await signIn("credentials", {
        redirect: false,
        access_token: accessToken,
        refresh_token: refreshToken,
      })

      if (signInResult?.error || !signInResult || signInResult.ok !== true) {
        setMfaError("MFA verified but session setup failed. Please sign in again.")
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
        })
        setOrgId(user.tenant_id)
        setEntityId(user.entity_roles.at(0)?.entity_id ?? null)
      }
      navigateAfterAuth(callbackUrl)
    } catch (error) {
      const message = error instanceof Error ? error.message.toLowerCase() : ""
      if (message.includes("expired")) {
        setMfaError("MFA session expired. Please sign in again.")
        return
      }
      if (
        message.includes("invalid totp") ||
        message.includes("verification code")
      ) {
        setMfaError("Invalid verification code")
        return
      }
      setMfaError("Unable to verify MFA right now. Please try again.")
    } finally {
      setIsMfaSubmitting(false)
    }
  })

  // ---- render -------------------------------------------------------------

  const stepSubtitle =
    step === 1
      ? "Use your admin-provisioned account credentials."
      : step === 2
        ? "Enter your password to continue."
        : "Enter the 6-digit code from your authenticator app."

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
        {/* Back chevron — steps 2 and 3 */}
        {step > 1 && (
          <button
            type="button"
            onClick={() => goToStep(step === 3 ? 2 : 1)}
            className="mb-4 flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Go back"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </button>
        )}

        <div className="mb-6 space-y-1">
          <h2 className="text-xl font-semibold text-foreground">Sign in to Finqor</h2>
          <p className="text-sm text-muted-foreground">{stepSubtitle}</p>
        </div>

        {/* Animated step container */}
        <div
          className="transition-opacity duration-150"
          style={{ opacity: visible ? 1 : 0 }}
        >
          {/* ---- Step 1: email + SSO ---- */}
          {step === 1 && (
            <div className="space-y-4">
              {registered ? (
                <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                  <p className="text-sm text-green-400">
                    Account created successfully. Please sign in.
                  </p>
                </div>
              ) : null}
              {reset ? (
                <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-3">
                  <p className="text-sm text-green-400">
                    Password reset successful. Please sign in.
                  </p>
                </div>
              ) : null}

              <Button
                variant="outline"
                className="w-full"
                type="button"
                onClick={() => void signIn("google")}
              >
                <GoogleIcon />
                <span className="ml-2">Continue with Google</span>
              </Button>

              <div className="relative my-4">
                <hr className="border-border" />
                <span className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 bg-card px-2 text-xs text-muted-foreground">
                  or
                </span>
              </div>

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

              {formError ? (
                <p role="alert" aria-live="polite" className="text-sm text-destructive">{formError}</p>
              ) : null}

              <Button
                className="h-10 w-full"
                type="button"
                onClick={onContinue}
              >
                Continue
              </Button>

              <p className="mt-4 text-center text-sm text-gray-400">
                Don&apos;t have an account?{" "}
                <Link href="/register" className="text-blue-400 hover:text-blue-300">
                  Create one free
                </Link>
              </p>
            </div>
          )}

          {/* ---- Step 2: password ---- */}
          {step === 2 && (
            <form className="space-y-4" onSubmit={onSignIn}>
              {/* Read-only email display */}
              <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2">
                <span className="text-sm text-foreground truncate">{storedEmail}</span>
                <button
                  type="button"
                  onClick={() => goToStep(1)}
                  className="ml-2 shrink-0 text-xs text-muted-foreground underline hover:text-foreground transition-colors"
                >
                  Change
                </button>
              </div>

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
                  autoFocus
                  aria-describedby={formError ? "password-error" : undefined}
                  {...register("password")}
                />
              </FormField>

              <div className="flex justify-end">
                <Link
                  href="/forgot-password"
                  className="text-sm text-gray-400 hover:text-blue-400"
                >
                  Forgot password?
                </Link>
              </div>

              {formError ? (
                <p id="password-error" role="alert" aria-live="polite" className="text-sm text-destructive">
                  {formError}
                </p>
              ) : null}

              <Button
                className="h-10 w-full"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          )}

          {/* ---- Step 3: inline MFA ---- */}
          {step === 3 && (
            <form className="space-y-5" onSubmit={onMfaVerify}>
              <div className="space-y-2">
                <InputOTP
                  maxLength={6}
                  value={mfaCode}
                  onChange={(value) =>
                    setMfaValue("code", value.replace(/\D/g, "").slice(0, 6))
                  }
                >
                  <InputOTPGroup>
                    <InputOTPSlot index={0} />
                    <InputOTPSlot index={1} />
                    <InputOTPSlot index={2} />
                    <InputOTPSlot index={3} />
                    <InputOTPSlot index={4} />
                    <InputOTPSlot index={5} />
                  </InputOTPGroup>
                </InputOTP>
              </div>

              {mfaError ? (
                <p className="text-sm text-destructive">{mfaError}</p>
              ) : null}

              <Button
                className="h-10 w-full"
                type="submit"
                disabled={isMfaSubmitting}
              >
                {isMfaSubmitting ? "Verifying..." : "Verify"}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
