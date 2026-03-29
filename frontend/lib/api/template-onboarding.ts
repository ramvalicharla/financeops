import apiClient from "@/lib/api/client"
import type {
  ApplyTemplateResponse,
  OnboardingState,
  OnboardingTemplateDetail,
  OnboardingTemplateSummary,
} from "@/lib/types/template-onboarding"

export const fetchOnboardingState = async (): Promise<OnboardingState> => {
  const response = await apiClient.get<OnboardingState>("/api/v1/onboarding/state")
  return response.data
}

export const patchOnboardingState = async (body: {
  current_step?: number
  industry?: string
  erp_connected?: boolean
}): Promise<OnboardingState> => {
  const response = await apiClient.patch<OnboardingState>("/api/v1/onboarding/state", body)
  return response.data
}

export const fetchOnboardingTemplates = async (): Promise<OnboardingTemplateSummary[]> => {
  const response = await apiClient.get<OnboardingTemplateSummary[]>("/api/v1/onboarding/templates")
  return response.data
}

export const fetchOnboardingTemplate = async (
  templateId: string,
): Promise<OnboardingTemplateDetail> => {
  const response = await apiClient.get<OnboardingTemplateDetail>(
    `/api/v1/onboarding/templates/${templateId}`,
  )
  return response.data
}

export const applyOnboardingTemplate = async (
  templateId: string,
): Promise<ApplyTemplateResponse> => {
  const response = await apiClient.post<ApplyTemplateResponse>("/api/v1/onboarding/apply", {
    template_id: templateId,
  })
  return response.data
}

export const completeOnboarding = async (): Promise<OnboardingState> => {
  const response = await apiClient.post<OnboardingState>("/api/v1/onboarding/complete")
  return response.data
}
