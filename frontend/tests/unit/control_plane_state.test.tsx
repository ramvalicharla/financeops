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
const getControlPlaneContext = vi.fn()

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}))

vi.mock("@/lib/api/control-plane", () => ({
  getControlPlaneContext: (...args: unknown[]) => getControlPlaneContext(...args),
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
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      selected_subject_type: null,
      selected_subject_id: null,
      intent_payload: null,
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
        module_key: "erp",
        module_name: "ERP",
        module_code: null,
        source: "requested_workspace",
      },
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

  it("keeps module visibility dependent on backend context", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <ModuleTabs />
      </QueryClientProvider>,
    )

    expect(await screen.findByText(/waiting for backend module context/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText("ERP")).toBeInTheDocument()
      expect(screen.queryByText("Accounting")).not.toBeInTheDocument()
    })
  })

  it("renders org and period from backend context instead of local store values", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    ;(useControlPlaneStore.setState as unknown as (state: Record<string, unknown>) => void)({
      current_org: "stale-org",
      current_module: "Stale Module",
      current_period: "1999-01",
    })

    render(
      <QueryClientProvider client={queryClient}>
        <ContextBar tenantSlug="acme" />
      </QueryClientProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText(/Acme Group/i)).toBeInTheDocument()
      expect(screen.getByText(/Acme India/i)).toBeInTheDocument()
      expect(screen.getByText(/^ERP$/i)).toBeInTheDocument()
      expect(screen.getByText(/Apr 2026/i)).toBeInTheDocument()
    })
    expect(screen.queryByText("stale-org")).not.toBeInTheDocument()
    expect(screen.queryByText("Stale Module")).not.toBeInTheDocument()
    expect(screen.queryByText("1999-01")).not.toBeInTheDocument()
  })
})
