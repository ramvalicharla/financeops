export type OnboardingIndustry =
  | "saas"
  | "manufacturing"
  | "retail"
  | "professional_services"
  | "healthcare"
  | "general"
  | "it_services"

export interface OnboardingState {
  id: string
  tenant_id: string
  current_step: number
  industry: OnboardingIndustry | null
  template_applied: boolean
  template_applied_at: string | null
  template_id: string | null
  erp_connected: boolean
  completed: boolean
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface OnboardingTemplateSummary {
  id: string
  name: string
  industry: OnboardingIndustry
  description: string
  board_pack_sections_count: number
  report_definitions_count: number
}

export interface OnboardingTemplateDetail {
  id: string
  name: string
  industry: OnboardingIndustry
  description: string
  board_pack_sections: Array<Record<string, unknown>>
  report_definitions: Array<Record<string, unknown>>
  delivery_schedule: Record<string, unknown>
}

export interface ApplyTemplateResponse {
  board_pack_definition_id: string
  report_definition_ids: string[]
  delivery_schedule_id: string
  step: number
}
