"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getSession, signIn } from "next-auth/react"
import { useRouter, useSearchParams } from "next/navigation"
import { StepIndicator } from "@/components/ui/StepIndicator"
import { Step1GroupIdentity } from "@/components/org-setup/Step1GroupIdentity"
import { Step2Entities } from "@/components/org-setup/Step2Entities"
import { Step3Ownership } from "@/components/org-setup/Step3Ownership"
import { Step4AccountingTools } from "@/components/org-setup/Step4AccountingTools"
import { Step5InviteTeam } from "@/components/org-setup/Step5InviteTeam"
import { SetupComplete } from "@/components/org-setup/SetupComplete"
import {
  getOrgSetupSummary,
  submitOrgSetupStep1,
  submitOrgSetupStep2,
  submitOrgSetupStep3,
  submitOrgSetupStep4,
  type Step2EntityPayload,
} from "@/lib/api/orgSetup"
import { navigateAfterAuth, waitForEstablishedSession } from "@/lib/auth-handoff"
import { useTenantStore } from "@/lib/store/tenant"

export default function OrgSetupPageClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const setTenant = useTenantStore((state) => state.setTenant)
  const tenantState = useTenantStore((state) => state)

  const [step2Draft, setStep2Draft] = useState<Step2EntityPayload[]>([])
  // localStep tracks UI-only step 5 (Invite team) which has no backend mutation
  const [localStep, setLocalStep] = useState<5 | null>(null)

  const summaryQuery = useQuery({
    queryKey: ["org-setup-summary"],
    queryFn: getOrgSetupSummary,
  })

  const backendStep = useMemo(() => {
    const nextStep = summaryQuery.data?.current_step ?? 1
    return Math.min(Math.max(nextStep, 1), 4)
  }, [summaryQuery.data?.current_step])

  // Effective step: localStep overrides backendStep for the UI-only step 5
  const currentStep: number = localStep ?? backendStep

  const setupComplete = Boolean(summaryQuery.data?.completed_at)
  const groupId = summaryQuery.data?.group?.id ?? null
  const entities = summaryQuery.data?.entities ?? []

  const refreshSessionAfterSetup = async () => {
    const currentSession = await getSession()
    if (!currentSession?.access_token || !currentSession.refresh_token) {
      return null
    }

    const signInResult = await signIn("credentials", {
      redirect: false,
      access_token: currentSession.access_token,
      refresh_token: currentSession.refresh_token,
    })

    if (!signInResult || signInResult.ok !== true || signInResult.error) {
      return null
    }

    return waitForEstablishedSession()
  }

  const step1Mutation = useMutation({
    mutationFn: submitOrgSetupStep1,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
    },
  })

  const step2Mutation = useMutation({
    mutationFn: (payload: Step2EntityPayload[]) =>
      submitOrgSetupStep2({
        group_id: groupId ?? "",
        entities: payload,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
    },
  })

  const step3Mutation = useMutation({
    mutationFn: submitOrgSetupStep3,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
    },
  })

  const step4Mutation = useMutation({
    mutationFn: submitOrgSetupStep4,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
      // Advance to local step 5 (Invite team) before navigating
      setLocalStep(5)
    },
  })

  const finishSetup = async () => {
    const refreshedSession = await refreshSessionAfterSetup()
    const user = refreshedSession?.user
    if (tenantState.tenant_id && tenantState.tenant_slug) {
      setTenant({
        tenant_id: tenantState.tenant_id,
        tenant_slug: tenantState.tenant_slug,
        org_setup_complete: user?.org_setup_complete ?? true,
        org_setup_step: user?.org_setup_step ?? 7,
        entity_roles: user?.entity_roles ?? tenantState.entity_roles,
        active_entity_id:
          user?.entity_roles.at(0)?.entity_id ?? tenantState.active_entity_id,
      })
    }
    navigateAfterAuth(nextPath)
  }

  const nextPath = useMemo(() => {
    const next = searchParams?.get("next")
    if (next && next.startsWith("/")) {
      return next
    }
    return "/dashboard"
  }, [searchParams])

  if (summaryQuery.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-14 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    )
  }

  if (summaryQuery.error) {
    return (
      <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm text-[hsl(var(--brand-danger))]">
        Failed to load organisation setup.
      </div>
    )
  }

  if (setupComplete) {
    return (
      <SetupComplete
        summary={summaryQuery.data}
        onEnter={() => {
          router.replace(nextPath)
        }}
      />
    )
  }

  return (
    <div className="space-y-5">
      <StepIndicator step={currentStep} />

      {currentStep === 1 ? (
        <Step1GroupIdentity
          submitting={step1Mutation.isPending}
          onSubmit={async (payload) => {
            await step1Mutation.mutateAsync(payload)
          }}
        />
      ) : null}

      {currentStep === 2 ? (
        <Step2Entities
          initial={step2Draft}
          submitting={step2Mutation.isPending}
          orgName={summaryQuery.data?.group?.group_name ?? "Your organisation"}
          onSubmit={async (payload) => {
            setStep2Draft(payload)
            await step2Mutation.mutateAsync(payload)
          }}
        />
      ) : null}

      {currentStep === 3 ? (
        <Step3Ownership
          entities={entities}
          submitting={step3Mutation.isPending}
          onSubmit={async (relationships) => {
            await step3Mutation.mutateAsync({ relationships })
          }}
        />
      ) : null}

      {currentStep === 4 ? (
        <>
          <Step4AccountingTools
            entities={entities}
            submitting={step4Mutation.isPending}
            onSubmit={async (configs) => {
              await step4Mutation.mutateAsync({ configs })
            }}
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setLocalStep(5)}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Skip for now
            </button>
          </div>
        </>
      ) : null}

      {currentStep === 5 ? (
        <Step5InviteTeam
          onSkip={finishSetup}
          onSubmit={finishSetup}
        />
      ) : null}
    </div>
  )
}
