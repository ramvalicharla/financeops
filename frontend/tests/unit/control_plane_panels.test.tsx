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
const listControlPlaneEntities = vi.fn()

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
  listControlPlaneEntities: (...args: unknown[]) => listControlPlaneEntities(...args),
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
      current_org: "acme",
      current_module: "Accounting",
      current_period: "2026-04",
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
      },
    ])
    getIntent.mockResolvedValue({
      intent_id: "intent-1",
      status: "RECORDED",
      job_id: "job-1",
      next_action: "NONE",
      record_refs: { journal_id: "journal-1" },
      guard_results: { overall_passed: true },
    })
    listControlPlaneEntities.mockResolvedValue([
      {
        id: "entity-1",
        entity_code: "ACME-001",
        entity_name: "Acme India",
        organisation_id: "org-1",
      },
    ])
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
    expect(screen.getByText("intent-1")).toBeInTheDocument()
    expect(screen.getByText("RECORDED")).toBeInTheDocument()
    expect(screen.getByText("job-1")).toBeInTheDocument()
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
  })
})
