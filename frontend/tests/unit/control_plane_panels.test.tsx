import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { JobPanel } from "@/components/panels/JobPanel"
import { IntentPanel } from "@/components/panels/IntentPanel"
import { Topbar } from "@/components/layout/Topbar"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const listJobs = vi.fn()
const getIntent = vi.fn()
const getControlPlaneContext = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounting/journals",
}))

vi.mock("@/components/notifications/NotificationBell", () => ({
  NotificationBell: () => <div>Notifications</div>,
}))

vi.mock("next-auth/react", () => ({
  signOut: vi.fn(),
}))

vi.mock("@/components/search/SearchProvider", () => ({
  useSearch: () => ({
    openPalette: vi.fn(),
  }),
}))

vi.mock("@/lib/api/control-plane", () => ({
  listJobs: (...args: unknown[]) => listJobs(...args),
  getIntent: (...args: unknown[]) => getIntent(...args),
  getControlPlaneContext: (...args: unknown[]) => getControlPlaneContext(...args),
}))

const renderWithProviders = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("control plane panels", () => {
  beforeEach(() => {
    sessionStorage.clear()
    useTenantStore.setState({
      tenant_id: "tenant-1",
      tenant_slug: "acme",
      org_setup_complete: true,
      org_setup_step: 7,
      active_entity_id: "entity-1",
      entity_roles: [],
    })
    useControlPlaneStore.setState({
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      intent_payload: null,
    })
    listJobs.mockResolvedValue([
      {
        job_id: "job-1",
        intent_id: "intent-1",
        entity_id: "entity-1",
        job_type: "POST_JOURNAL",
        status: "FAILED",
        runner_type: "inline",
        queue_name: "governed",
        requested_at: "2026-04-08T10:00:00Z",
        started_at: null,
        finished_at: null,
        failed_at: null,
        retry_count: 0,
        max_retries: 0,
        error_code: "ValidationError",
        error_message: "period locked",
        error_details: null,
        capabilities: {
          retry: {
            supported: false,
            allowed: false,
            reason: "Not supported in current backend contract",
          },
        },
      },
    ])
    getIntent.mockResolvedValue({
      intent_id: "intent-1",
      status: "RECORDED",
      payload: { operation: "submit" },
      job_id: "job-1",
      next_action: "NONE",
      record_refs: { journal_id: "journal-1" },
      guard_results: { overall_passed: true },
      events: [],
    })
    getControlPlaneContext.mockResolvedValue({
      tenant_id: "tenant-1",
      tenant_slug: "acme",
      current_organisation: {
        organisation_id: "org-1",
        organisation_name: "Acme Group",
        source: "org_group",
      },
      current_entity: {
        entity_id: "entity-1",
        entity_code: "ENT_ACME",
        entity_name: "Acme India",
        source: "requested_entity",
      },
      available_entities: [
        {
          entity_id: "entity-1",
          entity_code: "ENT_ACME",
          entity_name: "Acme India",
        },
      ],
      current_module: {
        module_key: "accounting",
        module_name: "Accounting",
        module_code: null,
        source: "requested_workspace",
      },
      workspace_tabs: [
        {
          workspace_key: "accounting",
          workspace_name: "Accounting",
          href: "/accounting/journals",
          match_prefixes: ["/accounting", "/fx"],
          module_codes: ["accounting_layer"],
        },
      ],
      enabled_modules: [],
      current_period: {
        period_label: "2026-04",
        fiscal_year: 2026,
        period_number: 4,
        source: "accounting_period",
        period_id: "period-1",
        status: "OPEN",
      },
    })
  })

  it("opens the intent panel and renders backend intent fields", async () => {
    useControlPlaneStore.getState().openIntentPanel({
      intent_id: "intent-1",
      status: "RECORDED",
      job_id: "job-1",
      next_action: "NONE",
      record_refs: { journal_id: "journal-1" },
    })

    renderWithProviders(<IntentPanel />)

    expect(await screen.findByText("Intent Panel")).toBeInTheDocument()
    expect(await screen.findByText("intent-1")).toBeInTheDocument()
    expect(screen.getByText("RECORDED")).toBeInTheDocument()
    expect(screen.getByText("job-1")).toBeInTheDocument()
    expect(screen.getByText(/operation/i)).toBeInTheDocument()
  })

  it("renders backend intent status instead of store payload status", async () => {
    useControlPlaneStore.getState().openIntentPanel({
      intent_id: "intent-1",
      status: "DRAFT",
      job_id: null,
      next_action: null,
      record_refs: null,
    })
    getIntent.mockResolvedValueOnce({
      intent_id: "intent-1",
      status: "APPROVED",
      payload: {},
      job_id: "job-1",
      next_action: "EXECUTE",
      record_refs: {},
      guard_results: { overall_passed: true },
      events: [],
    })

    renderWithProviders(<IntentPanel />)

    expect(await screen.findByText("APPROVED")).toBeInTheDocument()
    expect(screen.queryByText("DRAFT")).not.toBeInTheDocument()
  })

  it("opens the job panel from the top bar and renders failed jobs", async () => {
    const user = userEvent.setup()

    renderWithProviders(
      <>
        <Topbar
          entityRoles={[]}
          tenantSlug="acme"
          userEmail="leader@acme.test"
          userName="Finance Leader"
        />
        <JobPanel />
      </>,
    )

    await user.click(screen.getAllByText("Jobs")[0])

    await waitFor(() => {
      expect(screen.getByText("Job Panel")).toBeInTheDocument()
    })
    expect(screen.getByText("POST_JOURNAL")).toBeInTheDocument()
    expect(screen.getByText("FAILED")).toBeInTheDocument()
    expect(screen.getByText("period locked")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /retry unavailable/i })).toBeDisabled()
    expect(screen.getByText(/not supported in current backend contract/i)).toBeInTheDocument()
  })

  it("renders empty-state messaging when no jobs are returned", async () => {
    listJobs.mockResolvedValueOnce([])
    useControlPlaneStore.setState({ active_panel: "jobs" })

    renderWithProviders(<JobPanel />)

    expect(await screen.findByText(/no data yet/i)).toBeInTheDocument()
  })
})
