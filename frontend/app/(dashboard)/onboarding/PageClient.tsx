"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  applyOnboardingTemplate,
  completeOnboarding,
  fetchOnboardingState,
  fetchOnboardingTemplate,
  patchOnboardingState,
} from "@/lib/api/template-onboarding"
import { Step1Welcome } from "@/components/onboarding/Step1Welcome"
import { Step2Preview } from "@/components/onboarding/Step2Preview"
import { Step3Apply } from "@/components/onboarding/Step3Apply"
import { Step4Connect } from "@/components/onboarding/Step4Connect"
import { Step5Done } from "@/components/onboarding/Step5Done"
import { StepIndicator } from "@/components/ui/StepIndicator"
import type {
  ApplyTemplateResponse,
  OnboardingIndustry,
  OnboardingState,
  OnboardingTemplateDetail,
} from "@/lib/types/template-onboarding"

const normalizeTemplateId = (industry: OnboardingIndustry | null, templateId: string | null): string => {
  if (templateId && templateId.trim()) {
    return templateId
  }
  if (industry && industry.trim()) {
    return industry
  }
  return "general"
}

export default function OnboardingPage() {
  const [state, setState] = useState<OnboardingState | null>(null)
  const [currentStep, setCurrentStep] = useState<number>(1)
  const [selectedIndustry, setSelectedIndustry] = useState<OnboardingIndustry | null>(null)
  const [templateDetail, setTemplateDetail] = useState<OnboardingTemplateDetail | null>(null)
  const [loadingState, setLoadingState] = useState<boolean>(true)
  const [loadingTemplate, setLoadingTemplate] = useState<boolean>(false)
  const [stateError, setStateError] = useState<string | null>(null)
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [applyLoading, setApplyLoading] = useState<boolean>(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [applyResult, setApplyResult] = useState<ApplyTemplateResponse | null>(null)
  const [completeMessage, setCompleteMessage] = useState<string | null>(null)

  const completionSentRef = useRef<boolean>(false)

  const templateId = useMemo(
    () => normalizeTemplateId(selectedIndustry, state?.template_id ?? null),
    [selectedIndustry, state?.template_id],
  )

  const syncLocalState = useCallback((next: OnboardingState) => {
    setState(next)
    setCurrentStep(next.current_step)
    if (next.industry) {
      setSelectedIndustry(next.industry)
    }
  }, [])

  const loadState = useCallback(async () => {
    setLoadingState(true)
    setStateError(null)
    try {
      const payload = await fetchOnboardingState()
      syncLocalState(payload)
    } catch (cause) {
      setStateError(cause instanceof Error ? cause.message : "Failed to load onboarding state.")
    } finally {
      setLoadingState(false)
    }
  }, [syncLocalState])

  const loadTemplate = useCallback(async () => {
    if (currentStep < 2 || !templateId) return
    setLoadingTemplate(true)
    setTemplateError(null)
    try {
      const payload = await fetchOnboardingTemplate(templateId)
      setTemplateDetail(payload)
    } catch (cause) {
      setTemplateError(cause instanceof Error ? cause.message : "Failed to load template preview.")
      setTemplateDetail(null)
    } finally {
      setLoadingTemplate(false)
    }
  }, [currentStep, templateId])

  const patchState = useCallback(
    async (payload: { current_step?: number; industry?: string; erp_connected?: boolean }) => {
      const next = await patchOnboardingState(payload)
      syncLocalState(next)
      return next
    },
    [syncLocalState],
  )

  const runApply = useCallback(async () => {
    setApplyLoading(true)
    setApplyError(null)
    try {
      const payload = await applyOnboardingTemplate(templateId)
      setApplyResult(payload)
      const updated = await fetchOnboardingState()
      syncLocalState(updated)
    } catch (cause) {
      setApplyError(cause instanceof Error ? cause.message : "Failed to apply template.")
    } finally {
      setApplyLoading(false)
    }
  }, [syncLocalState, templateId])

  useEffect(() => {
    void loadState()
  }, [loadState])

  useEffect(() => {
    void loadTemplate()
  }, [loadTemplate])

  useEffect(() => {
    if (currentStep !== 3) return
    if (state?.template_applied && !applyResult) {
      setApplyResult({
        board_pack_definition_id: "existing",
        report_definition_ids: ["existing"],
        delivery_schedule_id: "existing",
        step: 3,
      })
      return
    }
    if (state?.template_applied) return
    if (applyLoading || applyResult) return
    void runApply()
  }, [applyLoading, applyResult, currentStep, runApply, state?.template_applied])

  useEffect(() => {
    if (currentStep !== 5 || completionSentRef.current) return
    completionSentRef.current = true
    void (async () => {
      try {
        const payload = await completeOnboarding()
        syncLocalState(payload)
        setCompleteMessage("Workspace setup marked complete.")
      } catch (cause) {
        setCompleteMessage(
          cause instanceof Error ? cause.message : "Could not mark onboarding as complete.",
        )
      }
    })()
  }, [currentStep, syncLocalState])

  if (loadingState) {
    return <div className="h-48 animate-pulse rounded-lg border border-border bg-muted/30" />
  }

  if (stateError) {
    return (
      <div className="space-y-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4">
        <p className="text-sm text-destructive">{stateError}</p>
        <button
          type="button"
          onClick={() => {
            void loadState()
          }}
          className="rounded-md border border-destructive/40 px-3 py-1 text-sm text-destructive"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <StepIndicator currentStep={currentStep} />

      {currentStep === 1 ? (
        <Step1Welcome
          selectedIndustry={selectedIndustry}
          onSelectIndustry={setSelectedIndustry}
          onContinue={() => {
            if (!selectedIndustry) return
            void patchState({ current_step: 2, industry: selectedIndustry })
          }}
          loading={loadingState}
        />
      ) : null}

      {currentStep === 2 ? (
        <Step2Preview
          template={templateDetail}
          loading={loadingTemplate}
          error={templateError}
          onBack={() => {
            void patchState({ current_step: 1 })
          }}
          onApply={() => {
            void patchState({ current_step: 3 })
          }}
        />
      ) : null}

      {currentStep === 3 ? (
        <Step3Apply
          loading={applyLoading}
          error={applyError}
          result={applyResult}
          onRetry={() => {
            setApplyResult(null)
            void runApply()
          }}
          onContinue={() => {
            void patchState({ current_step: 4 })
          }}
        />
      ) : null}

      {currentStep === 4 ? (
        <Step4Connect
          onSkip={() => {
            void patchState({ current_step: 5 })
          }}
          onConnected={() => {
            void patchState({ current_step: 5, erp_connected: true })
          }}
        />
      ) : null}

      {currentStep === 5 ? <Step5Done completionMessage={completeMessage} /> : null}
    </div>
  )
}
