"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { AlertCircle, CheckCircle2, ShieldCheck, Upload } from "lucide-react"
import { COUNTRY_OPTIONS, CURRENCY_OPTIONS, GAAP_OPTIONS } from "@/components/org-setup/constants"
import { CoaUploader } from "@/components/settings/CoaUploader"
import { ValidationPanel } from "@/components/settings/ValidationPanel"
import { FormField } from "@/components/ui/FormField"
import { StepIndicator } from "@/components/ui/StepIndicator"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { StructuredDataView } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  getCoaTemplates,
  uploadCoaFile,
  validateCoaFile,
  type CoaUploadMode,
  type CoaUploadResult,
} from "@/lib/api/coa"
import { getControlPlaneContext, listAirlockItems } from "@/lib/api/control-plane"
import {
  confirmOrgSetupStep1Draft,
  confirmOrgSetupStep2Draft,
  createOrgSetupStep1Draft,
  createOrgSetupStep2Draft,
  getOrgSetupSummary,
  reviewOrgSetupModuleSelection,
  type ApplicableGaap,
  type ModuleSelectionReview,
  type ReviewRow,
  type SetupIntentDraft,
  type Step2EntityPayload,
} from "@/lib/api/orgSetup"
import {
  listPlatformModules,
  togglePlatformModule,
  validatePlatformModuleToggle,
} from "@/lib/api/platform-admin"

const STEP_TITLES = [
  "Create Organization",
  "Create Entity",
  "Select Modules",
  "Upload Initial Data",
  "Completion",
] as const

const fiscalYearOptions = [
  { value: 1, label: "January" },
  { value: 4, label: "April" },
  { value: 7, label: "July" },
  { value: 10, label: "October" },
]

const explanationByStep: Record<number, { title: string; body: string; notes: string[] }> = {
  1: {
    title: "Organization scope",
    body: "This creates the group-level workspace the control plane anchors to.",
    notes: [
      "Your organization identity becomes the root for entities, modules, and reporting scope.",
      "Country and currency choices influence the default accounting context users see first.",
      "This step uses backend setup APIs only and does not simulate any state.",
    ],
  },
  2: {
    title: "Entity scope",
    body: "Entities define where journals, close, reconciliation, and reporting operate.",
    notes: [
      "Create at least one entity before moving into module and intake work.",
      "GAAP and fiscal-year settings shape the period context shown in the shell.",
      "The UI waits for the backend response before advancing to the next step.",
    ],
  },
  3: {
    title: "Module visibility",
    body: "This step reads and updates real backend module state instead of storing preferences locally.",
    notes: [
      "If your role cannot change module state, the backend response stays the source of truth.",
      "The module review in this step is read-only and does not turn module enablement into an intent execution flow yet.",
      "Enabled modules later drive the shell emphasis and the visible workspace tabs.",
      "There is no simulated module lifecycle on the client.",
    ],
  },
  4: {
    title: "Airlock-backed intake",
    body: "Initial data intake uses the existing upload path and then shows the resulting airlock queue state.",
    notes: [
      "Validation happens before apply so users can see what failed and what to do next.",
      "Onboarding uploads are tagged in backend airlock metadata so the origin stays visible.",
      "The queue below is loaded from the backend airlock APIs only.",
      "This keeps onboarding inside governed data-intake flows.",
    ],
  },
  5: {
    title: "Go live",
    body: "Completion summarizes the current backend truth for setup, module scope, and period context.",
    notes: [
      "The links below take users into the existing governed control-plane surfaces.",
      "If something is incomplete, users continue from the real module page instead of editing local state.",
      "This step is read-only and backend-driven.",
    ],
  },
}

interface MessageState {
  kind: "success" | "error"
  text: string
}

const fieldError = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback

export function OnboardingWizard() {
  const [step, setStep] = useState(1)
  const [message, setMessage] = useState<MessageState | null>(null)

  const [organizationName, setOrganizationName] = useState("")
  const [organizationWebsite, setOrganizationWebsite] = useState("")
  const [countryCode, setCountryCode] = useState("IN")
  const [functionalCurrency, setFunctionalCurrency] = useState("INR")
  const [reportingCurrency, setReportingCurrency] = useState("INR")
  const [organizationDraft, setOrganizationDraft] =
    useState<SetupIntentDraft<"create_organization"> | null>(null)

  const [entityPayload, setEntityPayload] = useState<Step2EntityPayload>({
    legal_name: "",
    display_name: "",
    entity_type: "WHOLLY_OWNED_SUBSIDIARY",
    country_code: "IN",
    state_code: "",
    functional_currency: "INR",
    reporting_currency: "INR",
    fiscal_year_start: 4,
    applicable_gaap: "INDAS",
    incorporation_number: "",
    pan: "",
    tan: "",
    cin: "",
    gstin: "",
    lei: "",
    tax_jurisdiction: "",
    tax_rate: "",
  })
  const [entityDraft, setEntityDraft] = useState<SetupIntentDraft<"create_entity"> | null>(null)
  const [moduleReview, setModuleReview] = useState<ModuleSelectionReview | null>(null)

  const [selectedTemplateId, setSelectedTemplateId] = useState("")
  const [uploadMode, setUploadMode] = useState<CoaUploadMode>("APPEND")
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<CoaUploadResult | null>(null)

  const summaryQuery = useQuery({
    queryKey: ["org-setup-summary", "product-onboarding"],
    queryFn: getOrgSetupSummary,
  })
  const modulesQuery = useQuery({
    queryKey: ["platform-modules", "product-onboarding"],
    queryFn: listPlatformModules,
  })
  const contextQuery = useQuery({
    queryKey: ["control-plane-context", "product-onboarding"],
    queryFn: () => getControlPlaneContext(),
    staleTime: 60_000,
  })
  const airlockQuery = useQuery({
    queryKey: ["control-plane-airlock", "product-onboarding"],
    queryFn: async () => listAirlockItems({ limit: 12 }),
  })
  const templatesQuery = useQuery({
    queryKey: ["coa-templates", "product-onboarding"],
    queryFn: getCoaTemplates,
  })

  const organizationPayload = useMemo(
    () => ({
      group_name: organizationName.trim(),
      country_of_incorp:
        COUNTRY_OPTIONS.find((option) => option.code === countryCode)?.label ?? "India",
      country_code: countryCode,
      functional_currency: functionalCurrency,
      reporting_currency: reportingCurrency,
      website: organizationWebsite.trim() || null,
      logo_url: null,
    }),
    [countryCode, functionalCurrency, organizationName, organizationWebsite, reportingCurrency],
  )

  const entitySubmissionPayload = useMemo(
    () => ({
      group_id: summaryQuery.data?.group?.id ?? "",
      entities: [
        {
          ...entityPayload,
          legal_name: entityPayload.legal_name.trim(),
          display_name: entityPayload.display_name?.trim() || null,
          state_code: entityPayload.state_code?.trim() || null,
          incorporation_number: entityPayload.incorporation_number?.trim() || null,
          pan: entityPayload.pan?.trim() || null,
          tan: entityPayload.tan?.trim() || null,
          cin: entityPayload.cin?.trim() || null,
          gstin: entityPayload.gstin?.trim() || null,
          lei: entityPayload.lei?.trim() || null,
          tax_jurisdiction: entityPayload.tax_jurisdiction?.trim() || null,
          tax_rate: entityPayload.tax_rate?.trim() || null,
        },
      ],
    }),
    [entityPayload, summaryQuery.data?.group?.id],
  )

  const organizationDraftMutation = useMutation({
    mutationFn: async () => createOrgSetupStep1Draft(organizationPayload),
    onSuccess: (draft) => {
      setOrganizationDraft(draft)
      setMessage({
        kind: "success",
        text: "Review before submit. This draft was generated by the backend and is ready for confirmation.",
      })
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to prepare organization review.") })
    },
  })

  const organizationConfirmMutation = useMutation({
    mutationFn: async () => {
      if (!organizationDraft) {
        throw new Error("Create a backend draft before confirming.")
      }
      return confirmOrgSetupStep1Draft(organizationDraft.draft_id)
    },
    onSuccess: async () => {
      const [summaryResult, contextResult] = await Promise.all([
        summaryQuery.refetch(),
        contextQuery.refetch(),
      ])
      const confirmed = Boolean(summaryResult.data?.group?.id) && Boolean(contextResult.data)
      setMessage({
        kind: "success",
        text: confirmed
          ? "Submitted to backend and confirmed by control plane. Continue to your first entity."
          : "Submitted to backend. Pending backend confirmation before this step is treated as complete.",
      })
      if (confirmed) {
        setOrganizationDraft(null)
        setStep(2)
      }
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to confirm organization draft.") })
    },
  })

  const entityDraftMutation = useMutation({
    mutationFn: async () => createOrgSetupStep2Draft(entitySubmissionPayload),
    onSuccess: (draft) => {
      setEntityDraft(draft)
      setMessage({
        kind: "success",
        text: "Review before submit. This entity draft was generated by the backend and is ready for confirmation.",
      })
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to prepare entity review.") })
    },
  })

  const entityConfirmMutation = useMutation({
    mutationFn: async () => {
      if (!entityDraft) {
        throw new Error("Create a backend draft before confirming.")
      }
      return confirmOrgSetupStep2Draft(entityDraft.draft_id)
    },
    onSuccess: async () => {
      const [summaryResult, contextResult] = await Promise.all([
        summaryQuery.refetch(),
        contextQuery.refetch(),
      ])
      const confirmed = Boolean(summaryResult.data?.entities.length) && Boolean(contextResult.data)
      setMessage({
        kind: "success",
        text: confirmed
          ? "Submitted to backend and confirmed by control plane. Select the modules you want visible."
          : "Submitted to backend. Pending backend confirmation before this entity is treated as active.",
      })
      if (confirmed) {
        setEntityDraft(null)
        setStep(3)
      }
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to confirm entity draft.") })
    },
  })

  const moduleToggleMutation = useMutation({
    mutationFn: async ({ moduleName, next }: { moduleName: string; next: boolean }) => {
      const validation = await validatePlatformModuleToggle(moduleName, {
        is_enabled: next,
        entity_id: summaryQuery.data?.entities[0]?.cp_entity_id ?? null,
      })
      if (!validation.success) {
        throw new Error(validation.reason ?? "Module change is unavailable in current backend contract.")
      }
      return togglePlatformModule(moduleName, next)
    },
    onSuccess: async (row) => {
      await Promise.all([modulesQuery.refetch(), contextQuery.refetch()])
      setModuleReview(null)
      setMessage({
        kind: "success",
        text: `${row.module_name} was submitted to backend module controls and refreshed from control-plane context.`,
      })
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to update module state.") })
    },
  })
  const moduleReviewMutation = useMutation({
    mutationFn: async () => reviewOrgSetupModuleSelection({ module_names: enabledModuleNames }),
    onSuccess: (review) => {
      setModuleReview(review)
      setMessage({
        kind: "success",
        text: "Review generated from backend-confirmed module state. Module enablement remains unavailable in the setup intent contract.",
      })
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Failed to prepare module review.") })
    },
  })

  const validateUploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("Select a file before validating.")
      return validateCoaFile(uploadFile, {
        origin_source: "onboarding",
        onboarding_step: "upload_initial_data",
      })
    },
    onSuccess: (result) => {
      setUploadResult(result as CoaUploadResult)
      setMessage({ kind: "success", text: "Validation completed. Review the results below." })
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Validation failed.") })
    },
  })

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("Select a file before uploading.")
      if (!selectedTemplateId) throw new Error("Choose a template before uploading.")
      return uploadCoaFile({
        file: uploadFile,
        template_id: selectedTemplateId,
        mode: uploadMode,
        origin_source: "onboarding",
        onboarding_step: "upload_initial_data",
      })
    },
    onSuccess: async (result) => {
      setUploadResult(result)
      const airlockResult = await airlockQuery.refetch()
      const confirmed = Boolean(airlockResult.data?.length)
      setMessage({
        kind: "success",
        text: confirmed
          ? "Submitted to backend and confirmed in the airlock queue. Review the current backend state before continuing."
          : "Submitted to backend. Pending airlock confirmation before this upload is treated as visible in the control plane.",
      })
      if (confirmed) {
        setStep(5)
      }
    },
    onError: (error) => {
      setMessage({ kind: "error", text: fieldError(error, "Upload failed.") })
    },
  })

  const progress = useMemo(() => Math.round((step / STEP_TITLES.length) * 100), [step])
  const enabledModules = contextQuery.data?.enabled_modules ?? []
  const enabledModuleNames = useMemo(
    () => modulesQuery.data?.filter((moduleRow) => moduleRow.is_enabled).map((moduleRow) => moduleRow.module_name) ?? [],
    [modulesQuery.data],
  )
  const currentPeriod = contextQuery.data?.current_period.period_label ?? "Unavailable"
  const organizationConfirmed = Boolean(summaryQuery.data?.group?.id)
  const entityConfirmed = Boolean(summaryQuery.data?.entities.length)
  const latestAirlockItem = airlockQuery.data?.[0] ?? null
  const uploadConfirmationLabel =
    latestAirlockItem?.status === "ADMITTED"
      ? "Confirmed by control plane"
      : latestAirlockItem
        ? "Submitted to backend - pending backend confirmation"
        : "No backend confirmation yet"
  const activeExplanation = explanationByStep[step]
  const onboardingFlowSteps = useMemo<FlowStripStep[]>(
    () => [
      {
        label: "Create organization",
        tone: organizationConfirmed ? "success" : step === 1 ? "active" : "default",
      },
      {
        label: "Create entity",
        tone: entityConfirmed ? "success" : step === 2 ? "active" : "default",
      },
      {
        label: "Select modules",
        tone: enabledModules.length > 0 ? "success" : step === 3 ? "active" : "default",
      },
      {
        label: "Upload initial data",
        tone:
          latestAirlockItem?.status === "ADMITTED"
            ? "success"
            : latestAirlockItem
              ? "warning"
              : step === 4
                ? "active"
                : "default",
      },
      {
        label: "Completion",
        tone: step === 5 ? "active" : "default",
      },
    ],
    [enabledModules.length, entityConfirmed, latestAirlockItem, organizationConfirmed, step],
  )
  const organizationReviewRows: ReviewRow[] = organizationDraft?.review_rows ?? [
    { label: "Legal name", value: organizationName.trim() || "Not provided yet" },
    { label: "Country", value: COUNTRY_OPTIONS.find((option) => option.code === countryCode)?.label ?? countryCode },
    { label: "Base currency", value: functionalCurrency },
    { label: "Reporting currency", value: reportingCurrency },
    { label: "Website", value: organizationWebsite.trim() || "Not provided yet" },
  ]
  const entityReviewRows: ReviewRow[] = entityDraft?.review_rows ?? [
    { label: "Legal name", value: entityPayload.legal_name.trim() || "Not provided yet" },
    { label: "Display name", value: entityPayload.display_name?.trim() || "Not provided yet" },
    { label: "Country", value: entityPayload.country_code || "Not provided yet" },
    { label: "Functional currency", value: entityPayload.functional_currency || "Not provided yet" },
    { label: "Reporting currency", value: entityPayload.reporting_currency || "Not provided yet" },
    { label: "Framework", value: entityPayload.applicable_gaap || "Not provided yet" },
  ]
  const uploadReview: ReviewRow[] = [
    { label: "Template", value: selectedTemplateId || "Select a template before submit" },
    { label: "Mode", value: uploadMode },
    { label: "File", value: uploadFile?.name ?? "No file selected" },
    { label: "Backend queue state", value: latestAirlockItem?.status ?? "No queue item yet" },
  ]
  const moduleReviewRows: ReviewRow[] = moduleReview?.review_rows ?? [
    {
      label: "Selected modules",
      value: enabledModuleNames.length ? enabledModuleNames.join(", ") : "No modules enabled in backend state yet",
    },
    {
      label: "Contract mode",
      value: "Reviewed only. Module enablement still uses existing backend APIs.",
    },
  ]
  const completionStats = useMemo(
    () => [
      { label: "Organization", value: summaryQuery.data?.group?.group_name ?? "Not created" },
      { label: "Entities", value: String(summaryQuery.data?.entities.length ?? 0) },
      { label: "Enabled modules", value: String(enabledModules.length) },
      { label: "Current period", value: currentPeriod },
    ],
    [currentPeriod, enabledModules.length, summaryQuery.data?.entities.length, summaryQuery.data?.group?.group_name],
  )
  const completionStatuses = useMemo(
    () => [
      {
        label: "Organization",
        value: organizationConfirmed ? "Confirmed by control plane" : "Submitted to backend",
      },
      {
        label: "Entity",
        value: entityConfirmed ? "Confirmed by control plane" : "Pending backend confirmation",
      },
      {
        label: "Modules",
        value: moduleReview
          ? "Reviewed from backend state and confirmed by control plane"
          : enabledModules.length
            ? "Confirmed by control plane"
            : "No enabled modules confirmed yet",
      },
      {
        label: "Initial data",
        value: uploadConfirmationLabel,
      },
    ],
    [enabledModules.length, entityConfirmed, moduleReview, organizationConfirmed, uploadConfirmationLabel],
  )

  const renderQueryMessage = (
    state: { isLoading: boolean; isError: boolean; error: Error | null },
    emptyMessage: string,
  ) => {
    if (state.isLoading) {
      return (
        <div className="rounded-2xl border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">
          Loading backend data...
        </div>
      )
    }
    if (state.isError) {
      return (
        <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm text-foreground">
          <p className="font-medium">Something failed</p>
          <p className="mt-1 text-muted-foreground">
            {state.error?.message ?? "The backend request did not complete."}
          </p>
          <p className="mt-2 text-muted-foreground">Refresh this step and try again.</p>
        </div>
      )
    }
    return (
      <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,hsl(var(--brand-primary)/0.12),transparent_34%),radial-gradient(circle_at_bottom_right,hsl(var(--brand-success)/0.12),transparent_28%),hsl(var(--background))] px-4 py-8 text-foreground sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-[2rem] border border-border/80 bg-card/95 p-6 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[hsl(var(--brand-primary))]">
                Product Onboarding
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                Bring the control plane to a usable first state
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
                This wizard keeps setup inside real backend flows: organization setup, entity creation,
                module enablement, and governed intake through airlock-backed upload.
              </p>
            </div>

            <div className="min-w-[260px] rounded-3xl border border-border bg-background/90 p-5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">Progress</span>
                <span className="text-muted-foreground">{progress}%</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                Step {step} of {STEP_TITLES.length}: <span className="text-foreground">{STEP_TITLES[step - 1]}</span>
              </p>
            </div>
          </div>

          <div className="mt-6">
            <StepIndicator currentStep={step} totalSteps={STEP_TITLES.length} />
          </div>
        </header>

        {message ? (
          <div
            className={`flex items-start gap-3 rounded-2xl border p-4 text-sm ${
              message.kind === "success"
                ? "border-[hsl(var(--brand-success)/0.35)] bg-[hsl(var(--brand-success)/0.12)]"
                : "border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)]"
            }`}
          >
            {message.kind === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--brand-success))]" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--brand-danger))]" />
            )}
            <div>
              <p className="font-medium text-foreground">
                {message.kind === "success" ? "Backend update" : "Action failed"}
              </p>
              <p className="mt-1 text-muted-foreground">{message.text}</p>
            </div>
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_360px]">
          <div className="space-y-6">
            {step === 1 ? (
              <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
                <FlowStrip
                  title="Workspace Flow"
                  subtitle="Create the organization root before you add entities, modules, or data."
                  steps={onboardingFlowSteps}
                />

                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold text-foreground">Create Organization</h2>
                  <p className="text-sm text-muted-foreground">
                    Start with the group-level identity that anchors entities, periods, and module context.
                  </p>
                </div>

                <section className="rounded-3xl border border-border bg-background/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {organizationReviewRows.map((row) => (
                      <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
                        <p className="mt-2 text-sm text-foreground">{row.value}</p>
                      </div>
                    ))}
                  </div>
                </section>

                <form
                  className="grid gap-4 md:grid-cols-2"
                  onSubmit={(event) => {
                    event.preventDefault()
                    if (organizationDraft) {
                      organizationConfirmMutation.mutate()
                      return
                    }
                    organizationDraftMutation.mutate()
                  }}
                >
                  <FormField id="organization-name" label="Organization legal name" required>
                    <Input
                      value={organizationName}
                      onChange={(event) => {
                        setOrganizationDraft(null)
                        setOrganizationName(event.target.value)
                      }}
                      placeholder="Acme Holdings Pvt Ltd"
                    />
                  </FormField>

                  <FormField id="organization-country" label="Country" required>
                    <select
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                      value={countryCode}
                      onChange={(event) => {
                        setOrganizationDraft(null)
                        setCountryCode(event.target.value)
                      }}
                    >
                      {COUNTRY_OPTIONS.map((option) => (
                        <option key={option.code} value={option.code}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </FormField>

                  <FormField id="organization-functional-currency" label="Base currency" required>
                    <select
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                      value={functionalCurrency}
                      onChange={(event) => {
                        setOrganizationDraft(null)
                        setFunctionalCurrency(event.target.value)
                      }}
                    >
                      {CURRENCY_OPTIONS.map((currency) => (
                        <option key={currency} value={currency}>
                          {currency}
                        </option>
                      ))}
                    </select>
                  </FormField>

                  <FormField id="organization-reporting-currency" label="Reporting currency" required>
                    <select
                      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                      value={reportingCurrency}
                      onChange={(event) => {
                        setOrganizationDraft(null)
                        setReportingCurrency(event.target.value)
                      }}
                    >
                      {CURRENCY_OPTIONS.map((currency) => (
                        <option key={currency} value={currency}>
                          {currency}
                        </option>
                      ))}
                    </select>
                  </FormField>

                  <div className="md:col-span-2">
                    <FormField id="organization-website" label="Website">
                      <Input
                        value={organizationWebsite}
                        onChange={(event) => {
                          setOrganizationDraft(null)
                          setOrganizationWebsite(event.target.value)
                        }}
                        placeholder="https://acme.example"
                      />
                    </FormField>
                  </div>

                  <div className="md:col-span-2 flex justify-end">
                    <Button
                      type="submit"
                      disabled={
                        organizationDraftMutation.isPending ||
                        organizationConfirmMutation.isPending ||
                        !organizationName.trim()
                      }
                    >
                      {organizationConfirmMutation.isPending
                        ? "Confirming..."
                        : organizationDraftMutation.isPending
                          ? "Preparing review..."
                          : organizationDraft
                            ? "Confirm with Backend"
                            : "Review Before Submit"}
                    </Button>
                  </div>
                </form>
              </section>
            ) : null}

            {step === 2 ? (
              <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
                <FlowStrip
                  title="Hierarchy Flow"
                  subtitle="Create the first legal entity so the shell can anchor journals, periods, and governance."
                  steps={onboardingFlowSteps}
                />

                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold text-foreground">Create Entity</h2>
                  <p className="text-sm text-muted-foreground">
                    Define the first operating entity so the workspace can show the right scope and framework.
                  </p>
                </div>

                <section className="rounded-3xl border border-border bg-background/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {entityReviewRows.map((row) => (
                      <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
                        <p className="mt-2 text-sm text-foreground">{row.value}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {!summaryQuery.data?.group?.id ? (
                  <div className="rounded-2xl border border-[hsl(var(--brand-warning)/0.4)] bg-[hsl(var(--brand-warning)/0.14)] p-4 text-sm text-foreground">
                    No organization has been saved yet. Start with step 1 before creating an entity.
                  </div>
                ) : (
                  <form
                    className="grid gap-4 md:grid-cols-2"
                    onSubmit={(event) => {
                      event.preventDefault()
                      if (entityDraft) {
                        entityConfirmMutation.mutate()
                        return
                      }
                      entityDraftMutation.mutate()
                    }}
                  >
                    <FormField id="entity-legal-name" label="Entity legal name" required>
                      <Input
                        value={entityPayload.legal_name}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return { ...current, legal_name: event.target.value }
                          })
                        }
                        placeholder="Acme India Pvt Ltd"
                      />
                    </FormField>

                    <FormField id="entity-display-name" label="Display name">
                      <Input
                        value={entityPayload.display_name ?? ""}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return { ...current, display_name: event.target.value }
                          })
                        }
                        placeholder="Acme India"
                      />
                    </FormField>

                    <FormField id="entity-country" label="Country" required>
                      <select
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        value={entityPayload.country_code}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return { ...current, country_code: event.target.value }
                          })
                        }
                      >
                        {COUNTRY_OPTIONS.map((option) => (
                          <option key={option.code} value={option.code}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField id="entity-functional-currency" label="Functional currency" required>
                      <select
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        value={entityPayload.functional_currency}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return {
                              ...current,
                              functional_currency: event.target.value,
                            }
                          })
                        }
                      >
                        {CURRENCY_OPTIONS.map((currency) => (
                          <option key={currency} value={currency}>
                            {currency}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField id="entity-reporting-currency" label="Reporting currency" required>
                      <select
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        value={entityPayload.reporting_currency}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return {
                              ...current,
                              reporting_currency: event.target.value,
                            }
                          })
                        }
                      >
                        {CURRENCY_OPTIONS.map((currency) => (
                          <option key={currency} value={currency}>
                            {currency}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField id="entity-fiscal-year" label="Fiscal year start" required>
                      <select
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        value={entityPayload.fiscal_year_start}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return {
                              ...current,
                              fiscal_year_start: Number(event.target.value),
                            }
                          })
                        }
                      >
                        {fiscalYearOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <FormField id="entity-gaap" label="Reporting framework" required>
                      <select
                        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                        value={entityPayload.applicable_gaap}
                        onChange={(event) =>
                          setEntityPayload((current) => {
                            setEntityDraft(null)
                            return {
                              ...current,
                              applicable_gaap: event.target.value as ApplicableGaap,
                            }
                          })
                        }
                      >
                        {GAAP_OPTIONS.map((gaap) => (
                          <option key={gaap} value={gaap}>
                            {gaap}
                          </option>
                        ))}
                      </select>
                    </FormField>

                    <div className="md:col-span-2 flex items-center justify-between">
                      <Button type="button" variant="outline" onClick={() => setStep(1)}>
                        Back
                      </Button>
                      <Button
                        type="submit"
                        disabled={
                          entityDraftMutation.isPending ||
                          entityConfirmMutation.isPending ||
                          !entityPayload.legal_name.trim()
                        }
                      >
                        {entityConfirmMutation.isPending
                          ? "Confirming..."
                          : entityDraftMutation.isPending
                            ? "Preparing review..."
                            : entityDraft
                              ? "Confirm with Backend"
                              : "Review Before Submit"}
                      </Button>
                    </div>
                  </form>
                )}
              </section>
            ) : null}

            {step === 3 ? (
              <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
                <FlowStrip
                  title="Module Flow"
                  subtitle="Choose which governed workspaces should be visible first. These switches call the backend registry."
                  steps={onboardingFlowSteps}
                />

                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold text-foreground">Select Modules</h2>
                  <p className="text-sm text-muted-foreground">
                    Enable only the modules your team needs first. The shell reflects what the backend exposes, and the review below is read-only.
                  </p>
                </div>

                <section className="rounded-3xl border border-border bg-background/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Backend review</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    This review is confirmed from backend state and does not replace the existing module enablement API.
                  </p>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {moduleReviewRows.map((row) => (
                      <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
                        <p className="mt-2 text-sm text-foreground">{row.value}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {modulesQuery.isLoading || modulesQuery.isError ? (
                  renderQueryMessage(
                    {
                      isLoading: modulesQuery.isLoading,
                      isError: modulesQuery.isError,
                      error: modulesQuery.error,
                    },
                    "No modules are available yet. Start by enabling one governed workspace.",
                  )
                ) : !modulesQuery.data?.length ? (
                  renderQueryMessage(
                    { isLoading: false, isError: false, error: null },
                    "No modules are available yet. Start by enabling one governed workspace.",
                  )
                ) : (
                  <div className="grid gap-4 md:grid-cols-2">
                    {modulesQuery.data.map((moduleRow) => (
                      <article key={moduleRow.id} className="rounded-3xl border border-border bg-background/80 p-5">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-2">
                            <h3 className="text-base font-semibold text-foreground">{moduleRow.module_name}</h3>
                            <p className="text-sm text-muted-foreground">
                              {moduleRow.description ?? "No description is available for this module yet."}
                            </p>
                          </div>
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-medium ${
                              moduleRow.is_enabled
                                ? "bg-[hsl(var(--brand-success)/0.14)] text-[hsl(var(--brand-success))]"
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {moduleRow.is_enabled ? "Enabled" : "Hidden"}
                          </span>
                        </div>

                        <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                          <span>Health: {moduleRow.health_status}</span>
                          <span>Version: {moduleRow.module_version}</span>
                        </div>

                        <div className="mt-5 flex items-center justify-between gap-3">
                          <p className="text-xs text-muted-foreground">
                            Route: {moduleRow.route_prefix ?? "Not published"}
                          </p>
                          <Button
                            variant={moduleRow.is_enabled ? "outline" : "default"}
                            onClick={() =>
                              moduleToggleMutation.mutate({
                                moduleName: moduleRow.module_name,
                                next: !moduleRow.is_enabled,
                              })
                            }
                            disabled={moduleToggleMutation.isPending}
                          >
                            {moduleRow.is_enabled ? "Disable" : "Enable"}
                          </Button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <Button type="button" variant="outline" onClick={() => setStep(2)}>
                    Back
                  </Button>
                  <div className="flex items-center gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => moduleReviewMutation.mutate()}
                      disabled={moduleReviewMutation.isPending}
                    >
                      {moduleReviewMutation.isPending ? "Reviewing..." : "Review Backend Selection"}
                    </Button>
                    <Button type="button" onClick={() => setStep(4)} disabled={!moduleReview && enabledModuleNames.length > 0}>
                      Continue to Upload
                    </Button>
                  </div>
                </div>
              </section>
            ) : null}

            {step === 4 ? (
              <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
                <FlowStrip
                  title="Upload Flow"
                  subtitle="Upload, validate, review the queue, and then let the governed processing continue."
                  steps={onboardingFlowSteps}
                />

                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold text-foreground">Upload Initial Data</h2>
                  <p className="text-sm text-muted-foreground">
                    Use the existing intake path to validate your starting chart of accounts and inspect the queue.
                  </p>
                </div>

                <section className="rounded-3xl border border-border bg-background/80 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {uploadReview.map((row) => (
                      <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
                        <p className="mt-2 text-sm text-foreground">{row.value}</p>
                      </div>
                    ))}
                  </div>
                </section>

                {templatesQuery.isLoading || templatesQuery.isError ? (
                  renderQueryMessage(
                    {
                      isLoading: templatesQuery.isLoading,
                      isError: templatesQuery.isError,
                      error: templatesQuery.error,
                    },
                    "No templates are available yet. Start by loading a chart-of-accounts template.",
                  )
                ) : (
                  <>
                    <CoaUploader
                      templates={templatesQuery.data ?? []}
                      selectedTemplateId={selectedTemplateId}
                      onTemplateChange={setSelectedTemplateId}
                      mode={uploadMode}
                      onModeChange={setUploadMode}
                      file={uploadFile}
                      onFileChange={setUploadFile}
                      onValidate={() => validateUploadMutation.mutate()}
                      onUpload={() => uploadMutation.mutate()}
                      validating={validateUploadMutation.isPending}
                      uploading={uploadMutation.isPending}
                    />

                    <ValidationPanel result={uploadResult} />
                  </>
                )}

                <section className="rounded-3xl border border-border bg-background/80 p-5">
                  <div className="flex items-center gap-2">
                    <Upload className="h-4 w-4 text-[hsl(var(--brand-primary))]" />
                    <h3 className="text-base font-semibold text-foreground">Airlock Queue</h3>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    This is the current queue state from the backend. Validation issues appear inside each item.
                  </p>

                  <div className="mt-4 space-y-3">
                    {airlockQuery.isLoading || airlockQuery.isError ? (
                      renderQueryMessage(
                        {
                          isLoading: airlockQuery.isLoading,
                          isError: airlockQuery.isError,
                          error: airlockQuery.error,
                        },
                        "No data has entered the airlock yet. Start by uploading a file.",
                      )
                    ) : !airlockQuery.data?.length ? (
                      renderQueryMessage(
                        { isLoading: false, isError: false, error: null },
                        "No data has entered the airlock yet. Start by uploading a file.",
                      )
                    ) : (
                      airlockQuery.data.map((item) => (
                        <article key={item.airlock_item_id} className="rounded-2xl border border-border bg-card p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium text-foreground">
                                {item.file_name ?? item.source_reference ?? item.airlock_item_id}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                Status: {item.status} - Source: {item.source_type}
                              </p>
                              {item.metadata?.source === "onboarding" ? (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  Origin: onboarding
                                  {typeof item.metadata.onboarding_step === "string"
                                    ? ` (${item.metadata.onboarding_step})`
                                    : ""}
                                </p>
                              ) : null}
                            </div>
                            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
                              {item.mime_type ?? "Unknown type"}
                            </span>
                          </div>

                          {item.findings.length ? (
                            <div className="mt-3 rounded-2xl border border-[hsl(var(--brand-warning)/0.4)] bg-[hsl(var(--brand-warning)/0.12)] p-3">
                              <p className="text-xs font-semibold uppercase tracking-wide text-foreground">
                                Validation issues
                              </p>
                              <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                                {item.findings.map((finding, index) => (
                                  <li key={`${item.airlock_item_id}-${index}`}>
                                    <StructuredDataView
                                      data={finding}
                                      emptyMessage="No structured finding details were returned."
                                      compact
                                    />
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : (
                            <p className="mt-3 text-sm text-muted-foreground">
                              No validation issues reported for this queue item yet.
                            </p>
                          )}
                        </article>
                      ))
                    )}
                  </div>
                </section>

                <div className="flex items-center justify-between">
                  <Button type="button" variant="outline" onClick={() => setStep(3)}>
                    Back
                  </Button>
                  <Button type="button" onClick={() => setStep(5)}>
                    Review Backend Confirmation
                  </Button>
                </div>
              </section>
            ) : null}

            {step === 5 ? (
              <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
                <FlowStrip
                  title="Go-Live View"
                  subtitle="This summary reads the current backend truth so the team can move into the control plane confidently."
                  steps={onboardingFlowSteps}
                />

                <div className="space-y-2">
                  <h2 className="text-2xl font-semibold text-foreground">Completion</h2>
                  <p className="text-sm text-muted-foreground">
                    Review the current backend-confirmed state, then continue into the governed workspaces.
                  </p>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {completionStats.map((stat) => (
                    <article key={stat.label} className="rounded-3xl border border-border bg-background/80 p-5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {stat.label}
                      </p>
                      <p className="mt-3 text-lg font-semibold text-foreground">{stat.value}</p>
                    </article>
                  ))}
                </div>

                <section className="rounded-3xl border border-border bg-background/70 p-5">
                  <h3 className="text-base font-semibold text-foreground">Backend confirmation</h3>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {completionStatuses.map((status) => (
                      <article key={status.label} className="rounded-2xl border border-border bg-card px-4 py-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {status.label}
                        </p>
                        <p className="mt-2 text-sm text-foreground">{status.value}</p>
                      </article>
                    ))}
                  </div>
                </section>

                <div className="rounded-3xl border border-border bg-background/70 p-5">
                  <h3 className="text-base font-semibold text-foreground">What to do next</h3>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Link href="/settings/control-plane" className="rounded-2xl border border-border bg-card px-4 py-4 text-sm text-foreground transition hover:border-[hsl(var(--brand-primary)/0.35)] hover:bg-[hsl(var(--brand-primary)/0.08)]">
                      Open Control Plane
                    </Link>
                    <Link href="/accounting/journals" className="rounded-2xl border border-border bg-card px-4 py-4 text-sm text-foreground transition hover:border-[hsl(var(--brand-primary)/0.35)] hover:bg-[hsl(var(--brand-primary)/0.08)]">
                      Review Journals
                    </Link>
                    <Link href="/settings/airlock" className="rounded-2xl border border-border bg-card px-4 py-4 text-sm text-foreground transition hover:border-[hsl(var(--brand-primary)/0.35)] hover:bg-[hsl(var(--brand-primary)/0.08)]">
                      Inspect Airlock
                    </Link>
                    <Link href="/reports" className="rounded-2xl border border-border bg-card px-4 py-4 text-sm text-foreground transition hover:border-[hsl(var(--brand-primary)/0.35)] hover:bg-[hsl(var(--brand-primary)/0.08)]">
                      Generate Reports
                    </Link>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <Button type="button" variant="outline" onClick={() => setStep(4)}>
                    Back
                  </Button>
                  <Button asChild>
                    <Link href="/settings/control-plane">Enter the Control Plane</Link>
                  </Button>
                </div>
              </section>
            ) : null}
          </div>

          <aside className="space-y-5">
            <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[hsl(var(--brand-primary))]" />
                <p className="text-sm font-semibold text-foreground">Explanation Panel</p>
              </div>
              <h2 className="mt-4 text-xl font-semibold text-foreground">{activeExplanation.title}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{activeExplanation.body}</p>
              <ul className="mt-4 space-y-3 text-sm text-muted-foreground">
                {activeExplanation.notes.map((note) => (
                  <li key={note} className="rounded-2xl border border-border bg-background/70 px-4 py-3">
                    {note}
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
              <p className="text-sm font-semibold text-foreground">Backend Truth</p>
              <div className="mt-4 space-y-3">
                {completionStats.map((stat) => (
                  <div key={stat.label} className="flex items-center justify-between rounded-2xl border border-border bg-background/70 px-4 py-3">
                    <span className="text-sm text-muted-foreground">{stat.label}</span>
                    <span className="text-sm font-medium text-foreground">{stat.value}</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
              <p className="text-sm font-semibold text-foreground">What happens next</p>
              <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                <div className="rounded-2xl border border-border bg-background/70 px-4 py-3">
                  Empty state guidance is visible when backend data has not been created yet.
                </div>
                <div className="rounded-2xl border border-border bg-background/70 px-4 py-3">
                  Loading and error states tell the user what failed and the next action to take.
                </div>
                <div className="rounded-2xl border border-border bg-background/70 px-4 py-3">
                  The shell, panels, and traceability views will read the same backend truth after onboarding.
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}
