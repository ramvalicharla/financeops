import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard"

const getOrgSetupSummary = vi.fn()
const createOrgSetupStep1Draft = vi.fn()
const confirmOrgSetupStep1Draft = vi.fn()
const createOrgSetupStep2Draft = vi.fn()
const confirmOrgSetupStep2Draft = vi.fn()
const reviewOrgSetupModuleSelection = vi.fn()
const listPlatformModules = vi.fn()
const togglePlatformModule = vi.fn()
const validatePlatformModuleToggle = vi.fn()
const getControlPlaneContext = vi.fn()
const listAirlockItems = vi.fn()
const getCoaTemplates = vi.fn()
const validateCoaFile = vi.fn()
const uploadCoaFile = vi.fn()

vi.mock("@/lib/api/orgSetup", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/orgSetup")>("@/lib/api/orgSetup")
  return {
    ...actual,
    getOrgSetupSummary: (...args: unknown[]) => getOrgSetupSummary(...args),
    createOrgSetupStep1Draft: (...args: unknown[]) => createOrgSetupStep1Draft(...args),
    confirmOrgSetupStep1Draft: (...args: unknown[]) => confirmOrgSetupStep1Draft(...args),
    createOrgSetupStep2Draft: (...args: unknown[]) => createOrgSetupStep2Draft(...args),
    confirmOrgSetupStep2Draft: (...args: unknown[]) => confirmOrgSetupStep2Draft(...args),
    reviewOrgSetupModuleSelection: (...args: unknown[]) => reviewOrgSetupModuleSelection(...args),
  }
})

vi.mock("@/lib/api/platform-admin", () => ({
  listPlatformModules: (...args: unknown[]) => listPlatformModules(...args),
  togglePlatformModule: (...args: unknown[]) => togglePlatformModule(...args),
  validatePlatformModuleToggle: (...args: unknown[]) => validatePlatformModuleToggle(...args),
}))

vi.mock("@/lib/api/control-plane", () => ({
  getControlPlaneContext: (...args: unknown[]) => getControlPlaneContext(...args),
  listAirlockItems: (...args: unknown[]) => listAirlockItems(...args),
}))

vi.mock("@/lib/api/coa", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/coa")>("@/lib/api/coa")
  return {
    ...actual,
    getCoaTemplates: (...args: unknown[]) => getCoaTemplates(...args),
    validateCoaFile: (...args: unknown[]) => validateCoaFile(...args),
    uploadCoaFile: (...args: unknown[]) => uploadCoaFile(...args),
  }
})

const renderWithProviders = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("onboarding wizard", () => {
  let summaryState: {
    group: { id: string; group_name: string } | null
    entities: Array<{ id: string; legal_name: string }>
    coa_status: string
    onboarding_score: number
  }
  let moduleState: Array<{
    id: string
    module_name: string
    module_version: string
    description: string | null
    is_enabled: boolean
    health_status: string
    route_prefix: string | null
    depends_on: string[]
    created_at: string
      updated_at: string
    }>
  let latestStep1Draft: { group_name: string } | null
  let latestStep2Draft: { entities: Array<{ legal_name: string }> } | null

  beforeEach(() => {
    vi.clearAllMocks()
    summaryState = {
      group: null,
      entities: [],
      coa_status: "pending",
      onboarding_score: 0,
    }
    moduleState = [
      {
        id: "module-1",
        module_name: "accounting_layer",
        module_version: "1.0.0",
        description: "Accounting workspace",
        is_enabled: false,
        health_status: "healthy",
        route_prefix: "/accounting",
        depends_on: [],
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]
    latestStep1Draft = null
    latestStep2Draft = null

    getOrgSetupSummary.mockImplementation(async () => ({
      group: summaryState.group,
      entities: summaryState.entities,
      ownership: [],
      erp_configs: [],
      current_step: summaryState.entities.length ? 3 : summaryState.group ? 2 : 1,
      completed_at: null,
      coa_account_count: 0,
      coa_status: summaryState.coa_status,
      onboarding_score: summaryState.onboarding_score,
      mapping_summary: {
        total: 0,
        mapped: 0,
        confirmed: 0,
        unmapped: 0,
        confidence_avg: "0",
      },
    }))
    createOrgSetupStep1Draft.mockImplementation(async (payload: { group_name: string }) => ({
      draft_id: "draft-step1",
      step: "create_organization",
      status: "draft",
      review_rows: [{ label: "Organization", value: payload.group_name }],
      payload: ((latestStep1Draft = payload), payload),
    }))
    confirmOrgSetupStep1Draft.mockImplementation(async () => {
      summaryState.group = { id: "group-1", group_name: latestStep1Draft?.group_name ?? "Acme Group" }
      summaryState.onboarding_score = 20
      return {
        draft_id: "draft-step1",
        step: "create_organization",
        status: "confirmed",
        review_rows: [{ label: "Organization", value: summaryState.group?.group_name ?? "" }],
        group: {
          id: "group-1",
          tenant_id: "tenant-1",
          group_name: summaryState.group?.group_name ?? "",
          country_of_incorp: "India",
          country_code: "IN",
          functional_currency: "INR",
          reporting_currency: "INR",
          logo_url: null,
          website: null,
          created_at: "2026-04-01T00:00:00Z",
          updated_at: null,
        },
      }
    })
    createOrgSetupStep2Draft.mockImplementation(async (payload: { entities: Array<{ legal_name: string }> }) => ({
      draft_id: "draft-step2",
      step: "create_entity",
      status: "draft",
      review_rows: [{ label: "Legal name", value: payload.entities[0].legal_name }],
      payload: ((latestStep2Draft = payload), payload),
    }))
    confirmOrgSetupStep2Draft.mockImplementation(async () => {
      summaryState.entities = [{ id: "entity-1", legal_name: latestStep2Draft?.entities[0].legal_name ?? "Acme India Pvt Ltd" }]
      summaryState.onboarding_score = 50
      return {
        draft_id: "draft-step2",
        step: "create_entity",
        status: "confirmed",
        review_rows: [{ label: "Legal name", value: summaryState.entities[0].legal_name }],
        entities: summaryState.entities,
      }
    })
    reviewOrgSetupModuleSelection.mockImplementation(async (payload: { module_names: string[] }) => ({
      draft_id: "draft-modules",
      step: "review_module_selection",
      status: "draft",
      review_rows: payload.module_names.length
        ? payload.module_names.map((moduleName, index) => ({
            label: `Module ${index + 1}`,
            value: moduleName,
          }))
        : [{ label: "Selected modules", value: "No modules enabled in backend state yet" }],
      payload: {
        module_names: payload.module_names,
        tenant_id: "tenant-1",
      },
      review_only: true,
    }))
    listPlatformModules.mockImplementation(async () => moduleState)
    validatePlatformModuleToggle.mockResolvedValue({
      success: true,
      failure: false,
      reason: null,
      module_name: "accounting_layer",
      entity_id: "entity-1",
    })
    togglePlatformModule.mockImplementation(async (moduleName: string, next: boolean) => {
      moduleState = moduleState.map((module) =>
        module.module_name === moduleName ? { ...module, is_enabled: next } : module,
      )
      return moduleState[0]
    })
    getControlPlaneContext.mockImplementation(async () => ({
      tenant_id: "tenant-1",
      tenant_slug: "acme",
      current_organisation: {
        organisation_id: "org-1",
        organisation_name: summaryState.group?.group_name ?? "Acme Group",
        source: "org_group",
      },
      current_entity: {
        entity_id: "entity-1",
        entity_code: "ENT_ACME",
        entity_name: summaryState.entities[0]?.legal_name ?? "Acme India Pvt Ltd",
        source: "requested_entity",
      },
      available_entities: [
        {
          entity_id: "entity-1",
          entity_code: "ENT_ACME",
          entity_name: summaryState.entities[0]?.legal_name ?? "Acme India Pvt Ltd",
        },
      ],
      current_module: {
        module_key: "accounting",
        module_name: "Accounting",
        module_code: null,
        source: "requested_workspace",
      },
      enabled_modules: moduleState
        .filter((module) => module.is_enabled)
        .map((module) => ({
          module_id: module.id,
          module_code: module.module_name,
          module_name: module.module_name,
          engine_context: "finance",
          is_financial_impacting: true,
          effective_from: "2026-04-01T00:00:00Z",
        })),
      current_period: {
        period_label: "2026-04",
        fiscal_year: 2026,
        period_number: 4,
        source: "accounting_period",
        period_id: "period-1",
        status: "OPEN",
      },
    }))
    listAirlockItems.mockResolvedValue([
      {
        airlock_item_id: "airlock-1",
        entity_id: "entity-1",
        source_type: "coa_upload",
        source_reference: "upload-1",
        file_name: "initial-coa.csv",
        mime_type: "text/csv",
        size_bytes: 128,
        checksum_sha256: "abc",
        status: "QUARANTINED",
        submitted_by_user_id: "user-1",
        reviewed_by_user_id: null,
        admitted_by_user_id: null,
        submitted_at: "2026-04-08T10:00:00Z",
        reviewed_at: null,
        admitted_at: null,
        rejected_at: null,
        rejection_reason: null,
        metadata: null,
        findings: [],
      },
    ])
    getCoaTemplates.mockResolvedValue([
      {
        id: "template-1",
        code: "IND",
        name: "India Template",
        description: null,
        is_active: true,
      },
    ])
    validateCoaFile.mockResolvedValue({
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      errors: [],
    })
    uploadCoaFile.mockResolvedValue({
      batch_id: "batch-1",
      upload_status: "UPLOADED",
      total_rows: 1,
      valid_rows: 1,
      invalid_rows: 0,
      errors: [],
    })
  })

  it("moves through backend-driven onboarding steps", async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingWizard />)

    expect(await screen.findByRole("heading", { name: "Create Organization" })).toBeInTheDocument()

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))

    expect(await screen.findByRole("heading", { name: "Create Entity" })).toBeInTheDocument()
    await user.type(screen.getByLabelText(/entity legal name/i), "Acme India Pvt Ltd")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))

    expect(await screen.findByRole("heading", { name: "Select Modules" })).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Enable" }))
    await user.click(screen.getByRole("button", { name: /review backend selection/i }))
    expect(
      await screen.findByText(
        /review generated from backend-confirmed module state\./i,
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /continue to upload/i }))

    expect(await screen.findByRole("heading", { name: "Upload Initial Data" })).toBeInTheDocument()
    expect(screen.getByText("Airlock Queue")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /review backend confirmation/i }))

    expect(await screen.findByRole("heading", { name: "Completion" })).toBeInTheDocument()
    expect(screen.getAllByText("Acme Group").length).toBeGreaterThan(0)
    expect(screen.getAllByText("2026-04").length).toBeGreaterThan(0)
    expect(screen.getByText(/submitted – pending backend confirmation/i)).toBeInTheDocument()
  })

  it("shows clear empty-state guidance when modules are unavailable", async () => {
    const user = userEvent.setup()
    moduleState = []

    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.type(await screen.findByLabelText(/entity legal name/i), "Acme India Pvt Ltd")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))

    await waitFor(() => {
      expect(screen.getByText(/no modules are available yet/i)).toBeInTheDocument()
    })
  })

  it("does not advance organization setup on optimistic local success alone", async () => {
    const user = userEvent.setup()
    createOrgSetupStep1Draft.mockResolvedValueOnce({
      draft_id: "draft-step1",
      step: "create_organization",
      status: "draft",
      review_rows: [{ label: "Organization", value: "Acme Group" }],
      payload: { group_name: "Acme Group" },
    })
    getOrgSetupSummary.mockResolvedValue({
      group: null,
      entities: [],
      ownership: [],
      erp_configs: [],
      current_step: 1,
      completed_at: null,
      coa_account_count: 0,
      coa_status: "pending",
      onboarding_score: 0,
      mapping_summary: {
        total: 0,
        mapped: 0,
        confirmed: 0,
        unmapped: 0,
        confidence_avg: "0",
      },
    })

    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))

    expect(await screen.findByText(/pending backend confirmation/i)).toBeInTheDocument()
    expect(screen.queryByRole("heading", { name: "Create Entity" })).not.toBeInTheDocument()
  })

  it("does not mark uploaded data as admitted without backend airlock confirmation", async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.type(await screen.findByLabelText(/entity legal name/i), "Acme India Pvt Ltd")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.click(screen.getByRole("button", { name: "Enable" }))
    await user.click(screen.getByRole("button", { name: /review backend selection/i }))
    await user.click(screen.getByRole("button", { name: /continue to upload/i }))
    await user.click(screen.getByRole("button", { name: /review backend confirmation/i }))

    expect(await screen.findByRole("heading", { name: "Completion" })).toBeInTheDocument()
    expect(screen.getByText(/submitted – pending backend confirmation/i)).toBeInTheDocument()
    expect(screen.queryByText(/admitted/i)).not.toBeInTheDocument()
  })

  it("does not call direct setup mutations outside the draft and confirm flow", async () => {
    const user = userEvent.setup()
    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))

    expect(createOrgSetupStep1Draft).toHaveBeenCalledTimes(1)
    expect(confirmOrgSetupStep1Draft).not.toHaveBeenCalled()
  })

  it("shows module validation failures returned by the backend contract", async () => {
    const user = userEvent.setup()
    validatePlatformModuleToggle.mockResolvedValueOnce({
      success: false,
      failure: true,
      reason: "Select an active entity before enabling a module during onboarding.",
      module_name: "accounting_layer",
      entity_id: null,
    })

    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.type(await screen.findByLabelText(/entity legal name/i), "Acme India Pvt Ltd")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.click(screen.getByRole("button", { name: "Enable" }))

    expect(await screen.findByText(/select an active entity before enabling a module during onboarding/i)).toBeInTheDocument()
    expect(togglePlatformModule).not.toHaveBeenCalled()
  })

  it("shows onboarding origin from backend airlock metadata", async () => {
    const user = userEvent.setup()
    listAirlockItems.mockResolvedValue([
      {
        airlock_item_id: "airlock-1",
        entity_id: "entity-1",
        source_type: "coa_upload",
        source_reference: "upload-1",
        file_name: "initial-coa.csv",
        mime_type: "text/csv",
        size_bytes: 128,
        checksum_sha256: "abc",
        status: "QUARANTINED",
        submitted_by_user_id: "user-1",
        reviewed_by_user_id: null,
        admitted_by_user_id: null,
        submitted_at: "2026-04-08T10:00:00Z",
        reviewed_at: null,
        admitted_at: null,
        rejected_at: null,
        rejection_reason: null,
        metadata: { source: "onboarding", onboarding_step: "upload_initial_data" },
        findings: [],
      },
    ])

    renderWithProviders(<OnboardingWizard />)

    await user.type(screen.getByLabelText(/organization.*name/i), "Acme Group")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.type(await screen.findByLabelText(/entity legal name/i), "Acme India Pvt Ltd")
    await user.click(screen.getByRole("button", { name: /review before submit/i }))
    await user.click(await screen.findByRole("button", { name: /confirm with backend/i }))
    await user.click(screen.getByRole("button", { name: "Enable" }))
    await user.click(screen.getByRole("button", { name: /review backend selection/i }))
    await user.click(screen.getByRole("button", { name: /continue to upload/i }))

    expect(await screen.findByText(/origin: onboarding \(upload_initial_data\)/i)).toBeInTheDocument()
  })
})
