"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { AlertCircle, CheckCircle2, ShieldCheck } from "lucide-react"
import { COUNTRY_OPTIONS, CURRENCY_OPTIONS } from "@/components/org-setup/constants"
import { StepIndicator } from "@/components/ui/StepIndicator"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { getCoaTemplates, uploadCoaFile, validateCoaFile, type CoaUploadMode, type CoaUploadResult } from "@/lib/api/coa"
import { getControlPlaneContext, listAirlockItems } from "@/lib/api/control-plane"
import { queryKeys } from "@/lib/query/keys"
import {
  confirmOrgSetupStep1Draft,
  confirmOrgSetupStep2Draft,
  createOrgSetupStep1Draft,
  createOrgSetupStep2Draft,
  getOrgSetupSummary,
  reviewOrgSetupModuleSelection,
  type ModuleSelectionReview,
  type ReviewRow,
  type SetupIntentDraft,
  type Step2EntityPayload,
} from "@/lib/api/orgSetup"
import { listPlatformModules, togglePlatformModule, validatePlatformModuleToggle } from "@/lib/api/platform-admin"
import { Step1CreateOrganization } from "./steps/Step1CreateOrganization"
import { Step2CreateEntity } from "./steps/Step2CreateEntity"
import { Step3SelectModules } from "./steps/Step3SelectModules"
import { Step4UploadData } from "./steps/Step4UploadData"
import { Step5Completion } from "./steps/Step5Completion"

const STEP_TITLES = ["Create Organization", "Create Entity", "Select Modules", "Upload Initial Data", "Completion"] as const

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
    ],
  },
  4: {
    title: "Airlock-backed intake",
    body: "Initial data intake uses the existing upload path and then shows the resulting airlock queue state.",
    notes: [
      "Validation happens before apply so users can see what failed and what to do next.",
      "Onboarding uploads are tagged in backend airlock metadata so the origin stays visible.",
      "The queue below is loaded from the backend airlock APIs only.",
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

interface MessageState { kind: "success" | "error"; text: string }
const fieldError = (err: unknown, fallback: string) => err instanceof Error ? err.message : fallback

export function OnboardingWizard() {
  const [step, setStep] = useState(1)
  const [message, setMessage] = useState<MessageState | null>(null)

  // ── Step 1 state ────────────────────────────────────────
  const [organizationName, setOrganizationName] = useState("")
  const [organizationWebsite, setOrganizationWebsite] = useState("")
  const [countryCode, setCountryCode] = useState("IN")
  const [functionalCurrency, setFunctionalCurrency] = useState("INR")
  const [reportingCurrency, setReportingCurrency] = useState("INR")
  const [organizationDraft, setOrganizationDraft] = useState<SetupIntentDraft<"create_organization"> | null>(null)

  // ── Step 2 state ────────────────────────────────────────
  const [entityPayload, setEntityPayload] = useState<Step2EntityPayload>({
    legal_name: "", display_name: "", entity_type: "WHOLLY_OWNED_SUBSIDIARY",
    country_code: "IN", state_code: "", functional_currency: "INR",
    reporting_currency: "INR", fiscal_year_start: 4, applicable_gaap: "INDAS",
    incorporation_number: "", pan: "", tan: "", cin: "", gstin: "", lei: "",
    tax_jurisdiction: "", tax_rate: "",
  })
  const [entityDraft, setEntityDraft] = useState<SetupIntentDraft<"create_entity"> | null>(null)
  const [moduleReview, setModuleReview] = useState<ModuleSelectionReview | null>(null)

  // ── Step 4 state ────────────────────────────────────────
  const [selectedTemplateId, setSelectedTemplateId] = useState("")
  const [uploadMode, setUploadMode] = useState<CoaUploadMode>("APPEND")
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<CoaUploadResult | null>(null)

  // ── Queries ─────────────────────────────────────────────
  const summaryQuery = useQuery({ queryKey: queryKeys.orgSetup.summary(), queryFn: getOrgSetupSummary })
  const modulesQuery = useQuery({ queryKey: queryKeys.platform.modules(), queryFn: listPlatformModules })
  const contextQuery = useQuery({ queryKey: queryKeys.workspace.context(), queryFn: () => getControlPlaneContext(), staleTime: 60_000 })
  const airlockQuery = useQuery({ queryKey: queryKeys.workspace.airlock(), queryFn: async () => listAirlockItems({ limit: 12 }) })
  const templatesQuery = useQuery({ queryKey: queryKeys.coa.templates(), queryFn: getCoaTemplates })

  // ── Computed payloads ─────────────────────────────────
  const organizationPayload = useMemo(() => ({
    group_name: organizationName.trim(),
    country_of_incorp: COUNTRY_OPTIONS.find((o) => o.code === countryCode)?.label ?? "India",
    country_code: countryCode,
    functional_currency: functionalCurrency,
    reporting_currency: reportingCurrency,
    website: organizationWebsite.trim() || null,
    logo_url: null,
  }), [countryCode, functionalCurrency, organizationName, organizationWebsite, reportingCurrency])

  const entitySubmissionPayload = useMemo(() => ({
    group_id: summaryQuery.data?.group?.id ?? "",
    entities: [{
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
    }],
  }), [entityPayload, summaryQuery.data?.group?.id])

  // ── Mutations ──────────────────────────────────────────
  const orgDraftMutation = useMutation({
    mutationFn: () => createOrgSetupStep1Draft(organizationPayload),
    onSuccess: (d) => { setOrganizationDraft(d); setMessage({ kind: "success", text: "Review before submit." }) },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to prepare organization review.") }),
  })

  const orgConfirmMutation = useMutation({
    mutationFn: async () => {
      if (!organizationDraft) throw new Error("Create a backend draft before confirming.")
      return confirmOrgSetupStep1Draft(organizationDraft.draft_id)
    },
    onSuccess: async () => {
      const [s, c] = await Promise.all([summaryQuery.refetch(), contextQuery.refetch()])
      const ok = Boolean(s.data?.group?.id) && Boolean(c.data)
      setMessage({ kind: "success", text: ok ? "Confirmed. Continue to your first entity." : "Submitted. Pending backend confirmation." })
      if (ok) { setOrganizationDraft(null); setStep(2) }
    },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to confirm organization draft.") }),
  })

  const entityDraftMutation = useMutation({
    mutationFn: () => createOrgSetupStep2Draft(entitySubmissionPayload),
    onSuccess: (d) => { setEntityDraft(d); setMessage({ kind: "success", text: "Review before submit." }) },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to prepare entity review.") }),
  })

  const entityConfirmMutation = useMutation({
    mutationFn: async () => {
      if (!entityDraft) throw new Error("Create a backend draft before confirming.")
      return confirmOrgSetupStep2Draft(entityDraft.draft_id)
    },
    onSuccess: async () => {
      const [s, c] = await Promise.all([summaryQuery.refetch(), contextQuery.refetch()])
      const ok = Boolean(s.data?.entities.length) && Boolean(c.data)
      setMessage({ kind: "success", text: ok ? "Confirmed. Select the modules you want visible." : "Submitted. Pending backend confirmation." })
      if (ok) { setEntityDraft(null); setStep(3) }
    },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to confirm entity draft.") }),
  })

  const enabledModuleNames = useMemo(
    () => modulesQuery.data?.filter((m) => m.is_enabled).map((m) => m.module_name) ?? [],
    [modulesQuery.data],
  )

  const moduleToggleMutation = useMutation({
    mutationFn: async ({ moduleName, next }: { moduleName: string; next: boolean }) => {
      const v = await validatePlatformModuleToggle(moduleName, { is_enabled: next, entity_id: summaryQuery.data?.entities[0]?.cp_entity_id ?? null })
      if (!v.success) throw new Error(v.reason ?? "Module change unavailable.")
      return togglePlatformModule(moduleName, next)
    },
    onSuccess: async (row) => {
      await Promise.all([modulesQuery.refetch(), contextQuery.refetch()])
      setModuleReview(null)
      setMessage({ kind: "success", text: `${row.module_name} was updated and refreshed from control-plane context.` })
    },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to update module state.") }),
  })

  const moduleReviewMutation = useMutation({
    mutationFn: () => reviewOrgSetupModuleSelection({ module_names: enabledModuleNames }),
    onSuccess: (r) => { setModuleReview(r); setMessage({ kind: "success", text: "Review generated from backend-confirmed module state." }) },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Failed to prepare module review.") }),
  })

  const validateUploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("Select a file before validating.")
      return validateCoaFile(uploadFile, { origin_source: "onboarding", onboarding_step: "upload_initial_data" })
    },
    onSuccess: (r) => { setUploadResult(r as CoaUploadResult); setMessage({ kind: "success", text: "Validation completed." }) },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Validation failed.") }),
  })

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("Select a file before uploading.")
      if (!selectedTemplateId) throw new Error("Choose a template before uploading.")
      return uploadCoaFile({ file: uploadFile, template_id: selectedTemplateId, mode: uploadMode, origin_source: "onboarding", onboarding_step: "upload_initial_data" })
    },
    onSuccess: async (r) => {
      setUploadResult(r)
      const al = await airlockQuery.refetch()
      const ok = Boolean(al.data?.length)
      setMessage({ kind: "success", text: ok ? "Submitted and confirmed in the airlock queue." : "Submitted. Pending airlock confirmation." })
      if (ok) setStep(5)
    },
    onError: (e) => setMessage({ kind: "error", text: fieldError(e, "Upload failed.") }),
  })

  // ── Derived display data ───────────────────────────────
  const enabledModules = contextQuery.data?.enabled_modules ?? []
  const latestAirlockItem = airlockQuery.data?.[0] ?? null
  const uploadConfirmationLabel =
    latestAirlockItem?.status === "ADMITTED"
      ? "Confirmed by control plane"
      : latestAirlockItem
        ? "Submitted – pending backend confirmation"
        : "No backend confirmation yet"

  const organizationConfirmed = Boolean(summaryQuery.data?.group?.id)
  const entityConfirmed = Boolean(summaryQuery.data?.entities.length)
  const progress = Math.round((step / STEP_TITLES.length) * 100)
  const currentPeriod = contextQuery.data?.current_period.period_label ?? "Unavailable"
  const activeExplanation = explanationByStep[step]

  const onboardingFlowSteps = useMemo<FlowStripStep[]>(() => [
    { label: "Create organization", tone: organizationConfirmed ? "success" : step === 1 ? "active" : "default" },
    { label: "Create entity", tone: entityConfirmed ? "success" : step === 2 ? "active" : "default" },
    { label: "Select modules", tone: enabledModules.length > 0 ? "success" : step === 3 ? "active" : "default" },
    { label: "Upload initial data", tone: latestAirlockItem?.status === "ADMITTED" ? "success" : latestAirlockItem ? "warning" : step === 4 ? "active" : "default" },
    { label: "Completion", tone: step === 5 ? "active" : "default" },
  ], [enabledModules.length, entityConfirmed, latestAirlockItem, organizationConfirmed, step])

  const organizationReviewRows: ReviewRow[] = organizationDraft?.review_rows ?? [
    { label: "Legal name", value: organizationName.trim() || "Not provided yet" },
    { label: "Country", value: COUNTRY_OPTIONS.find((o) => o.code === countryCode)?.label ?? countryCode },
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
    { label: "Selected modules", value: enabledModuleNames.length ? enabledModuleNames.join(", ") : "No modules enabled in backend state yet" },
    { label: "Contract mode", value: "Reviewed only. Module enablement still uses existing backend APIs." },
  ]

  const completionStats = useMemo(() => [
    { label: "Organization", value: summaryQuery.data?.group?.group_name ?? "Not created" },
    { label: "Entities", value: String(summaryQuery.data?.entities.length ?? 0) },
    { label: "Enabled modules", value: String(enabledModules.length) },
    { label: "Current period", value: currentPeriod },
  ], [currentPeriod, enabledModules.length, summaryQuery.data?.entities.length, summaryQuery.data?.group?.group_name])

  const completionStatuses = useMemo(() => [
    { label: "Organization", value: organizationConfirmed ? "Confirmed by control plane" : "Submitted to backend" },
    { label: "Entity", value: entityConfirmed ? "Confirmed by control plane" : "Pending backend confirmation" },
    { label: "Modules", value: moduleReview ? "Reviewed from backend state" : enabledModules.length ? "Confirmed by control plane" : "No enabled modules confirmed yet" },
    { label: "Initial data", value: uploadConfirmationLabel },
  ], [enabledModules.length, entityConfirmed, moduleReview, organizationConfirmed, uploadConfirmationLabel])

  const renderQueryMessage = (
    state: { isLoading: boolean; isError: boolean; error: Error | null },
    emptyMessage: string,
  ) => {
    if (state.isLoading) return <div className="rounded-2xl border border-dashed border-border bg-muted/40 p-4 text-sm text-muted-foreground">Loading backend data...</div>
    if (state.isError) return (
      <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm text-foreground">
        <p className="font-medium">Something failed</p>
        <p className="mt-1 text-muted-foreground">{state.error?.message ?? "The backend request did not complete."}</p>
      </div>
    )
    return <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">{emptyMessage}</div>
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,hsl(var(--brand-primary)/0.12),transparent_34%),radial-gradient(circle_at_bottom_right,hsl(var(--brand-success)/0.12),transparent_28%),hsl(var(--background))] px-4 py-8 text-foreground sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl space-y-6">
        {/* ── Header ─────────────────────────────────────────── */}
        <header className="rounded-[2rem] border border-border/80 bg-card/95 p-6 shadow-sm backdrop-blur">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[hsl(var(--brand-primary))]">Product Onboarding</p>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
                Bring the control plane to a usable first state
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
                This wizard keeps setup inside real backend flows: organization setup, entity creation, module enablement, and governed intake through airlock-backed upload.
              </p>
            </div>

            <div className="min-w-[260px] rounded-3xl border border-border bg-background/90 p-5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">Progress</span>
                <span className="text-muted-foreground">{progress}%</span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all" style={{ width: `${progress}%` }} />
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

        {/* ── Status Message ─────────────────────────────────── */}
        {message && (
          <div className={`flex items-start gap-3 rounded-2xl border p-4 text-sm ${message.kind === "success" ? "border-[hsl(var(--brand-success)/0.35)] bg-[hsl(var(--brand-success)/0.12)]" : "border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)]"}`}>
            {message.kind === "success"
              ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--brand-success))]" />
              : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--brand-danger))]" />
            }
            <div>
              <p className="font-medium text-foreground">{message.kind === "success" ? "Backend update" : "Action failed"}</p>
              <p className="mt-1 text-muted-foreground">{message.text}</p>
            </div>
          </div>
        )}

        {/* ── Body ───────────────────────────────────────────── */}
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_360px]">
          <div className="space-y-6">
            {step === 1 && (
              <Step1CreateOrganization
                flowSteps={onboardingFlowSteps}
                organizationName={organizationName}
                setOrganizationName={setOrganizationName}
                organizationWebsite={organizationWebsite}
                setOrganizationWebsite={setOrganizationWebsite}
                countryCode={countryCode}
                setCountryCode={setCountryCode}
                functionalCurrency={functionalCurrency}
                setFunctionalCurrency={setFunctionalCurrency}
                reportingCurrency={reportingCurrency}
                setReportingCurrency={setReportingCurrency}
                organizationDraft={organizationDraft}
                setOrganizationDraft={() => setOrganizationDraft(null)}
                organizationReviewRows={organizationReviewRows}
                onSubmit={() => { if (organizationDraft) { orgConfirmMutation.mutate() } else { orgDraftMutation.mutate() } }}
                isPendingDraft={orgDraftMutation.isPending}
                isPendingConfirm={orgConfirmMutation.isPending}
              />
            )}

            {step === 2 && (
              <Step2CreateEntity
                flowSteps={onboardingFlowSteps}
                entityPayload={entityPayload}
                setEntityPayload={setEntityPayload}
                entityDraft={entityDraft}
                setEntityDraft={() => setEntityDraft(null)}
                entityReviewRows={entityReviewRows}
                hasOrganization={Boolean(summaryQuery.data?.group?.id)}
                onBack={() => setStep(1)}
                onSubmit={() => { if (entityDraft) { entityConfirmMutation.mutate() } else { entityDraftMutation.mutate() } }}
                isPendingDraft={entityDraftMutation.isPending}
                isPendingConfirm={entityConfirmMutation.isPending}
              />
            )}

            {step === 3 && (
              <Step3SelectModules
                flowSteps={onboardingFlowSteps}
                modulesLoading={modulesQuery.isLoading}
                modulesError={modulesQuery.isError}
                modulesData={modulesQuery.data}
                moduleReview={moduleReview}
                moduleReviewRows={moduleReviewRows}
                enabledModuleNames={enabledModuleNames}
                onBack={() => setStep(2)}
                onNext={() => setStep(4)}
                onToggle={(name, next) => moduleToggleMutation.mutate({ moduleName: name, next })}
                onReview={() => moduleReviewMutation.mutate()}
                isTogglingModule={moduleToggleMutation.isPending}
                isReviewing={moduleReviewMutation.isPending}
                renderQueryMessage={renderQueryMessage}
              />
            )}

            {step === 4 && (
              <Step4UploadData
                flowSteps={onboardingFlowSteps}
                uploadReview={uploadReview}
                templatesLoading={templatesQuery.isLoading}
                templatesError={templatesQuery.isError}
                templates={templatesQuery.data ?? []}
                selectedTemplateId={selectedTemplateId}
                setSelectedTemplateId={setSelectedTemplateId}
                uploadMode={uploadMode}
                setUploadMode={setUploadMode}
                uploadFile={uploadFile}
                setUploadFile={setUploadFile}
                uploadResult={uploadResult}
                airlockLoading={airlockQuery.isLoading}
                airlockError={airlockQuery.isError}
                airlockData={airlockQuery.data}
                onValidate={() => validateUploadMutation.mutate()}
                onUpload={() => uploadMutation.mutate()}
                isValidating={validateUploadMutation.isPending}
                isUploading={uploadMutation.isPending}
                onBack={() => setStep(3)}
                onNext={() => setStep(5)}
                renderQueryMessage={renderQueryMessage}
              />
            )}

            {step === 5 && (
              <Step5Completion
                flowSteps={onboardingFlowSteps}
                completionStats={completionStats}
                completionStatuses={completionStatuses}
                onBack={() => setStep(4)}
              />
            )}
          </div>

          {/* ── Sidebar: Explanation + Backend Truth ───────── */}
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
                  <li key={note} className="rounded-2xl border border-border bg-background/70 px-4 py-3">{note}</li>
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
                {[
                  "Empty state guidance is visible when backend data has not been created yet.",
                  "Loading and error states tell the user what failed and the next action to take.",
                  "The shell, panels, and traceability views will read the same backend truth after onboarding.",
                ].map((note) => (
                  <div key={note} className="rounded-2xl border border-border bg-background/70 px-4 py-3">{note}</div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}
