"use client"

import Link from "next/link"
import { Suspense, useState } from "react"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { signIn } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"
import apiClient from "@/lib/api/client"
import { Button } from "@/components/ui/button"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import { navigateAfterAuth, waitForEstablishedSession } from "@/lib/auth-handoff"
import { getSafeCallbackUrl } from "@/lib/login-flow"
import { useTenantStore } from "@/lib/store/tenant"
import { useWorkspaceStore } from "@/lib/store/workspace"

const mfaSchema = z.object({
  code: z
    .string()
    .length(6, "Enter the 6-digit verification code")
    .regex(/^\d{6}$/, "Code must contain only digits"),
})

type MFAVerifyForm = z.infer<typeof mfaSchema>

export default function MFAPage() {
  return (
    <Suspense fallback={null}>
      <MFAPageContent />
    </Suspense>
  )
}

function MFAPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const setTenant = useTenantStore((state) => state.setTenant)
  const { setOrgId, setEntityId } = useWorkspaceStore()
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const challengeToken = searchParams?.get("challenge")?.trim() ?? null
  const callbackUrl = getSafeCallbackUrl(searchParams?.get("callbackUrl"))

  const { handleSubmit, setValue, watch } = useForm<MFAVerifyForm>({
    defaultValues: { code: "" },
  })

  const code = watch("code")

  const verify = handleSubmit(async (values) => {
    if (isSubmitting) {
      return
    }

    setFormError(null)
    const parsed = mfaSchema.safeParse(values)
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid verification code")
      return
    }
    if (!challengeToken) {
      setFormError("MFA session expired or missing. Please sign in again.")
      console.debug("[mfa-page] missing mfa token", {
        hasMfaToken: false,
      })
      return
    }

    setIsSubmitting(true)
    try {
      const verifyPayload = {
        mfa_challenge_token: challengeToken,
        totp_code: parsed.data.code,
      }
      console.debug("[mfa-page] submitting mfa verify", {
        hasMfaToken: Boolean(challengeToken),
        payload: verifyPayload,
      })

      const verifyResponse = await apiClient.post<{
        access_token?: string
        refresh_token?: string
      }>("/api/v1/auth/mfa/verify", verifyPayload)
      console.debug("[mfa-page] backend mfa verify response", verifyResponse)

      const accessToken = verifyResponse.data?.access_token
      const refreshToken = verifyResponse.data?.refresh_token
      if (!accessToken || !refreshToken) {
        setFormError("Unable to verify MFA right now. Please try again.")
        return
      }

      const signInResult = await signIn("credentials", {
        redirect: false,
        access_token: accessToken,
        refresh_token: refreshToken,
      })
      console.debug("[mfa-page] session sign-in result", signInResult)

      if (signInResult?.error || !signInResult || signInResult.ok !== true) {
        setFormError("MFA verified but session setup failed. Please sign in again.")
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
          active_entity_id: user.entity_roles.at(0)?.entity_id ?? null,
        })
        setOrgId(user.tenant_id)
        setEntityId(user.entity_roles.at(0)?.entity_id ?? null)
      }
      navigateAfterAuth(callbackUrl)
    } catch (error) {
      console.debug("[mfa-page] mfa verify threw", error)
      const message = error instanceof Error ? error.message.toLowerCase() : ""
      if (message.includes("expired")) {
        setFormError("MFA session expired. Please sign in again.")
        return
      }
      if (message.includes("invalid totp") || message.includes("verification code")) {
        setFormError("Invalid verification code")
        return
      }
      if (message.includes("mfa is not configured")) {
        setFormError("MFA is not configured for this account. Please sign in again.")
        return
      }
      setFormError("Unable to verify MFA right now. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  })

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 space-y-1">
        <h2 className="text-xl font-semibold text-foreground">
          Two-factor authentication
        </h2>
        <p className="text-sm text-muted-foreground">
          Enter the 6-digit code from your authenticator app.
        </p>
      </div>

      <form className="space-y-5" onSubmit={verify}>
        <div className="space-y-2">
          <InputOTP
            maxLength={6}
            value={code}
            onChange={(value) => setValue("code", value.replace(/\D/g, "").slice(0, 6))}
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

        {formError ? <p className="text-sm text-destructive">{formError}</p> : null}

        <Button className="h-10 w-full" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Verifying..." : "Verify"}
        </Button>
      </form>

      <div className="mt-4 text-center text-sm">
        <Link className="text-muted-foreground underline" href="/login">
          Back to login
        </Link>
      </div>
    </div>
  )
}
