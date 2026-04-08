import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { EntitySwitcher } from "@/components/layout/EntitySwitcher"
import { ModuleTabs } from "@/components/layout/ModuleTabs"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const mockPathname = vi.fn(() => "/erp/sync")

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
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
    expect(useControlPlaneStore.getState().current_period).toBe("2026-04")
  })
})
