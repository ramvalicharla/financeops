import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ContextBar } from "@/components/layout/ContextBar"
import { ModuleTabs } from "@/components/layout/ModuleTabs"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const mockOpenPalette = vi.fn()
const mockPathname = vi.fn(() => "/accounting/journals")

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}))

vi.mock("next-auth/react", () => ({
  signOut: vi.fn(),
}))

vi.mock("@/components/search/SearchProvider", () => ({
  useSearch: () => ({
    openPalette: mockOpenPalette,
  }),
}))

vi.mock("@/components/notifications/NotificationBell", () => ({
  NotificationBell: () => <div>Notifications</div>,
}))

vi.mock("@/hooks/useBilling", () => ({
  useCurrentEntitlements: () => ({
    data: null,
    isPending: false,
    isLoading: false,
  }),
}))

vi.mock("@/lib/api/control-plane", () => ({
  listControlPlaneEntities: vi.fn(async () => [
    {
      id: "entity-1",
      entity_code: "ACME-001",
      entity_name: "Acme India",
      organisation_id: "org-1",
    },
  ]),
  getControlPlaneContext: vi.fn(async () => ({
    tenant_id: "tenant-1",
    tenant_slug: "acme",
    current_organisation: {
      organisation_id: "org-1",
      organisation_name: "Acme Group",
      source: "org_group",
    },
    current_entity: {
      entity_id: "entity-1",
      entity_code: "ACME-001",
      entity_name: "Acme India",
      source: "requested_entity",
    },
    available_entities: [
      {
        entity_id: "entity-1",
        entity_code: "ACME-001",
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
    enabled_modules: [
      {
        module_id: "mod-1",
        module_code: "accounting_layer",
        module_name: "Accounting",
        engine_context: "finance",
        is_financial_impacting: true,
        effective_from: "2026-04-01T00:00:00Z",
      },
    ],
    current_period: {
      period_label: "2026-04",
      fiscal_year: 2026,
      period_number: 4,
      source: "accounting_period",
      period_id: "period-1",
      status: "OPEN",
    },
  })),
}))

const renderWithQueryClient = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("control plane shell", () => {
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
  })

  it("renders shell context from backend-confirmed organization, entity, module, and period", async () => {
    renderWithQueryClient(
      <>
        <Sidebar
          entityRoles={[]}
          userRole="finance_leader"
          tenantId="tenant-1"
          tenantSlug="acme"
          orgSetupComplete
          orgSetupStep={7}
          userEmail="leader@acme.test"
          userName="Finance Leader"
        />
        <Topbar
          entityRoles={[]}
          tenantSlug="acme"
          userEmail="leader@acme.test"
          userName="Finance Leader"
        />
        <ModuleTabs />
        <ContextBar tenantSlug="acme" />
      </>,
    )

    expect(screen.getAllByText("Finqor").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Jobs")[0]).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getAllByText(/Acme Group/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/Acme India/i).length).toBeGreaterThan(0)
      expect(screen.getAllByText(/^Accounting$/i).length).toBeGreaterThan(0)
      expect(screen.getByText("2026-04")).toBeInTheDocument()
    })
  })

  it("does not let stale control-plane store context override backend context", async () => {
    ;(useControlPlaneStore.setState as unknown as (state: Record<string, unknown>) => void)({
      current_org: "stale-org",
      current_module: "Stale Module",
      current_period: "1999-01",
    })

    renderWithQueryClient(
      <>
        <ModuleTabs />
        <ContextBar tenantSlug="acme" />
      </>,
    )

    await waitFor(() => {
      expect(screen.getAllByText(/Acme Group/i).length).toBeGreaterThan(0)
      expect(screen.getByText(/Acme India/i)).toBeInTheDocument()
      expect(screen.getByText("2026-04")).toBeInTheDocument()
    })
    expect(screen.queryByText("stale-org")).not.toBeInTheDocument()
    expect(screen.queryByText("Stale Module")).not.toBeInTheDocument()
    expect(screen.queryByText("1999-01")).not.toBeInTheDocument()
  })
})
