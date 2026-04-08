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
      current_org: "acme",
      current_module: "Accounting",
      current_period: "2026-04",
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      intent_payload: null,
    })
  })

  it("renders left nav, top bar, module tabs, and context bar with period", async () => {
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

    expect(screen.getAllByText("FinanceOps").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Jobs")[0]).toBeInTheDocument()
    expect(screen.getByText("Accounting")).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/Period: Apr 2026/i)).toBeInTheDocument()
    })
  })
})
