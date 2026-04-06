"use client"

import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter, useSearchParams } from "next/navigation"
import { StepIndicator } from "@/components/ui/StepIndicator"
import { Step1GroupIdentity } from "@/components/org-setup/Step1GroupIdentity"
import { Step2Entities } from "@/components/org-setup/Step2Entities"
import { Step3Ownership } from "@/components/org-setup/Step3Ownership"
import { Step4AccountingTools } from "@/components/org-setup/Step4AccountingTools"
import { Step5IndustryCoA } from "@/components/org-setup/Step5IndustryCoA"
import { Step6ErpMapping } from "@/components/org-setup/Step6ErpMapping"
import { SetupComplete } from "@/components/org-setup/SetupComplete"
import {
  getOrgSetupProgress,
  getOrgSetupSummary,
  listOrgEntities,
  submitOrgSetupStep1,
  submitOrgSetupStep2,
  submitOrgSetupStep3,
  submitOrgSetupStep4,
  submitOrgSetupStep5,
  submitOrgSetupStep6,
  type Step2EntityPayload,
} from "@/lib/api/orgSetup"
import { getCoaTemplates } from "@/lib/api/coa"
import { useTenantStore } from "@/lib/store/tenant"

export default function OrgSetupPageClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()
  const setTenant = useTenantStore((state) => state.setTenant)
  const tenantState = useTenantStore((state) => state)

  const [currentStep, setCurrentStep] = useState(1)
  const [groupId, setGroupId] = useState<string | null>(null)
  const [step2Draft, setStep2Draft] = useState<Step2EntityPayload[]>([])
  const [setupComplete, setSetupComplete] = useState(false)

  const progressQuery = useQuery({
    queryKey: ["org-setup-progress"],
    queryFn: getOrgSetupProgress,
  })

  const entitiesQuery = useQuery({
    queryKey: ["org-setup-entities"],
    queryFn: listOrgEntities,
    enabled: setupComplete || currentStep >= 3,
  })

  const templatesQuery = useQuery({
    queryKey: ["org-setup-templates"],
    queryFn: getCoaTemplates,
    enabled: currentStep >= 5,
  })

  const summaryQuery = useQuery({
    queryKey: ["org-setup-summary"],
    queryFn: getOrgSetupSummary,
    enabled: setupComplete || currentStep === 5,
  })

  useEffect(() => {
    if (!progressQuery.data) {
      return
    }
    const nextGroupId =
      progressQuery.data.step1_data && typeof progressQuery.data.step1_data.group_id === "string"
        ? progressQuery.data.step1_data.group_id
        : null
    if (nextGroupId) {
      setGroupId((previous) => previous ?? nextGroupId)
    }
    if (progressQuery.data.completed_at) {
      setSetupComplete((previous) => previous || true)
      return
    }
    const nextStep = Math.min(Math.max(progressQuery.data.current_step || 1, 1), 6)
    setCurrentStep((previous) => (previous === nextStep ? previous : nextStep))
  }, [progressQuery.data])

  const step1Mutation = useMutation({
    mutationFn: submitOrgSetupStep1,
    onSuccess: (group) => {
      setGroupId(group.id)
      setCurrentStep(2)
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
    },
  })

  const step2Mutation = useMutation({
    mutationFn: (payload: Step2EntityPayload[]) =>
      submitOrgSetupStep2({
        group_id: groupId ?? "",
        entities: payload,
      }),
    onSuccess: () => {
      setCurrentStep(3)
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
      void queryClient.invalidateQueries({ queryKey: ["org-setup-entities"] })
    },
  })

  const step3Mutation = useMutation({
    mutationFn: submitOrgSetupStep3,
    onSuccess: () => {
      setCurrentStep(4)
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
    },
  })

  const step4Mutation = useMutation({
    mutationFn: submitOrgSetupStep4,
    onSuccess: () => {
      setCurrentStep(5)
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
    },
  })

  const step5Mutation = useMutation({
    mutationFn: submitOrgSetupStep5,
    onSuccess: () => {
      setCurrentStep(6)
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
      void queryClient.invalidateQueries({ queryKey: ["org-setup-entities"] })
      void queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
    },
  })

  const step6Mutation = useMutation({
    mutationFn: submitOrgSetupStep6,
    onSuccess: () => {
      setSetupComplete(true)
      if (tenantState.tenant_id && tenantState.tenant_slug) {
        setTenant({
          tenant_id: tenantState.tenant_id,
          tenant_slug: tenantState.tenant_slug,
          org_setup_complete: true,
          org_setup_step: 7,
          entity_roles: tenantState.entity_roles,
          active_entity_id: tenantState.active_entity_id,
        })
      }
      void queryClient.invalidateQueries({ queryKey: ["org-setup-progress"] })
      void queryClient.invalidateQueries({ queryKey: ["org-setup-summary"] })
    },
  })

  const nextPath = useMemo(() => {
    const next = searchParams?.get("next")
    if (next && next.startsWith("/")) {
      return next
    }
    return "/dashboard"
  }, [searchParams])

  if (progressQuery.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-14 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    )
  }

  if (progressQuery.error) {
    return (
      <div className="rounded-xl border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm text-[hsl(var(--brand-danger))]">
        Failed to load organisation setup progress.
      </div>
    )
  }

  const entities = entitiesQuery.data ?? []

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
        <Step4AccountingTools
          entities={entities}
          submitting={step4Mutation.isPending}
          onSubmit={async (configs) => {
            await step4Mutation.mutateAsync({ configs })
          }}
        />
      ) : null}

      {currentStep === 5 ? (
        <Step5IndustryCoA
          entities={entities}
          templates={templatesQuery.data ?? []}
          submitting={step5Mutation.isPending}
          onSubmit={async (entityTemplates) => {
            await step5Mutation.mutateAsync({ entity_templates: entityTemplates })
          }}
        />
      ) : null}

      {currentStep === 6 ? (
        <Step6ErpMapping
          entities={entities}
          submitting={step6Mutation.isPending}
          onSubmit={async (payload) => {
            await step6Mutation.mutateAsync(payload)
          }}
        />
      ) : null}
    </div>
  )
}
