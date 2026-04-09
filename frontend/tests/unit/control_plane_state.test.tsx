import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { ModuleTabs } from "@/components/layout/ModuleTabs"
import { ContextBar } from "@/components/layout/ContextBar"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const mockPathname = vi.fn(() => "/erp/sync")

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}))

vi.mock("@/lib/api/control-plane", () => ({
  getControlPlaneContext: vi.fn(async () => ({
    tenant_id: "tenant-1",
    tenant_slug: "acme",
    enabled_modules: [
      {
        module_id: "mod-erp",
        module_code: "erp_sync",
        module_name: "ERP Sync",
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
  listControlPlaneEntities: vi.fn(async () => [
    {
      id: "entity-1",
      entity_code: "ACME-001",
      entity_name: "Acme India",
      organisation_id: "org-1",
    },
  ]),
}))

describe("control plane state", () => {
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
      current_module: null,
      current_period: "2026-04",
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      intent_payload: null,
    })
  })

  it("updates active entity from the entity switcher", async () => {
    const user = userEvent.setup()
    render(
      <EntitySwitcher
        entityRoles={[
          { entity_id: "entity-1", entity_name: "Acme India", role: null },
          { entity_id: "entity-2", entity_name: "Acme Holdings", role: null },
        ]}
      />,
    )

    await user.selectOptions(screen.getByLabelText(/select active scope/i), "entity-2")

    expect(useTenantStore.getState().active_entity_id).toBe("entity-2")
  })

  it("keeps module state synchronized with the active tab and period visible in store", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <ModuleTabs />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(useControlPlaneStore.getState().current_module).toBe("ERP")
    })
    await waitFor(() => {
      expect(useControlPlaneStore.getState().current_period).toBe("2026-04")
      expect(screen.getByText("ERP")).toBeInTheDocument()
    })
    expect(screen.queryByText("Accounting")).not.toBeInTheDocument()
  })

  it("hydrates current period from backend context instead of browser time", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    useControlPlaneStore.setState({ current_period: null })

    render(
      <QueryClientProvider client={queryClient}>
        <ContextBar tenantSlug="acme" />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(useControlPlaneStore.getState().current_period).toBe("2026-04")
    })
  })
})
