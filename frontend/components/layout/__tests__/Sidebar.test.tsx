import { render, screen } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import type { Mock } from "vitest"
import { Sidebar } from "../Sidebar"

// ── Next.js / Auth mocks ────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({ usePathname: () => "/dashboard" }))
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))
vi.mock("next-auth/react", () => ({ signOut: vi.fn() }))

// ── Sub-component mocks — avoid their own hook requirements ─────────────────

vi.mock("@/components/layout/_components/SidebarNavGroup", () => ({
  SidebarNavGroup: ({
    items,
    pathname: _pathname,
  }: {
    items: { id: string; label: string; href: string }[]
    pathname: string
  }) => (
    <ul>
      {items.map((item) => (
        <li key={item.id} data-testid={`nav-item-${item.id}`}>
          {item.label}
        </li>
      ))}
    </ul>
  ),
}))

vi.mock("@/components/ui/skeleton", () => ({ Skeleton: () => null }))
vi.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
}))

// ── Store mocks ─────────────────────────────────────────────────────────────

vi.mock("@/lib/store/tenant", () => ({
  useTenantStore: vi.fn(),
}))

vi.mock("@/lib/store/ui", () => ({
  useUIStore: vi.fn(),
}))

vi.mock("@/lib/store/workspace", () => ({
  useWorkspaceStore: vi.fn(),
}))

vi.mock("@/hooks/useBilling", () => ({
  useCurrentEntitlements: vi.fn().mockReturnValue({
    data: [],
    isPending: false,
    isLoading: false,
  }),
}))

// ── API / Query mocks ───────────────────────────────────────────────────────

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = (await importOriginal()) as object
  return {
    ...actual,
    useQuery: vi.fn().mockReturnValue({ data: undefined, isLoading: false }),
  }
})

vi.mock("@/lib/api/control-plane", () => ({
  listControlPlaneEntities: vi.fn().mockResolvedValue([]),
  getControlPlaneContext: vi.fn().mockResolvedValue(null),
}))

vi.mock("@/lib/query/keys", () => ({
  queryKeys: {
    workspace: {
      entities: () => ["workspace", "entities"],
      context: (id: string | null) => ["workspace", "context", id],
    },
  },
}))

// ── Test helpers ────────────────────────────────────────────────────────────

import { useWorkspaceStore } from "@/lib/store/workspace"
import { useUIStore } from "@/lib/store/ui"
import { useTenantStore } from "@/lib/store/tenant"

function mockStores({ sidebarCollapsed = false } = {}) {
  const workspaceState = {
    sidebarCollapsed,
    sidebarOpen: false,
    entityId: null,
    orgId: "org-001",
    period: "2025-2026",
    toggleSidebar: vi.fn(),
    switchEntity: vi.fn(),
    setOrgId: vi.fn(),
    setEntityId: vi.fn(),
  }
  ;(useWorkspaceStore as unknown as Mock).mockImplementation(
    (selector?: (s: typeof workspaceState) => unknown) =>
      selector ? selector(workspaceState) : workspaceState,
  )
  ;(useUIStore as unknown as Mock).mockImplementation((selector?: (s: unknown) => unknown) => {
    const state = {
      sidebarOpen: false,
      closeSidebar: vi.fn(),
      billingWarning: null,
      billingWarningDismissed: false,
      dismissBillingWarning: vi.fn(),
    }
    return selector ? selector(state) : state
  })
  ;(useTenantStore as unknown as Mock).mockImplementation(
    (selector?: (s: unknown) => unknown) => {
      const state = { setTenant: vi.fn() }
      return selector ? selector(state) : state
    },
  )
}

const defaultProps = {
  tenantId: "tenant-001",
  tenantSlug: "acme",
  orgSetupComplete: true,
  orgSetupStep: 7,
  userName: "Test User",
  userEmail: "test@acme.com",
  userRole: "finance_leader" as const,
  entityRoles: [],
}

// ── Tests ───────────────────────────────────────────────────────────────────

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStores()
  })

  it("renders all three group labels in expanded mode", () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText("Workspace")).toBeInTheDocument()
    expect(screen.getByText("Org")).toBeInTheDocument()
    expect(screen.getByText("Governance")).toBeInTheDocument()
  })

  it("does not render group header labels in collapsed (rail) mode", () => {
    mockStores({ sidebarCollapsed: true })
    render(<Sidebar {...defaultProps} />)
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument()
    expect(screen.queryByText("Org")).not.toBeInTheDocument()
    expect(screen.queryByText("Governance")).not.toBeInTheDocument()
  })

  it("renders all 12 nav items under their groups when not filtered", () => {
    render(<Sidebar {...defaultProps} />)
    // Workspace (4)
    expect(screen.getByText("Overview")).toBeInTheDocument()
    expect(screen.getByText("Today's focus")).toBeInTheDocument()
    expect(screen.getByText("Period close")).toBeInTheDocument()
    expect(screen.getByText("Approvals")).toBeInTheDocument()
    // Org (5)
    expect(screen.getByText("Entities")).toBeInTheDocument()
    expect(screen.getByText("Org settings")).toBeInTheDocument()
    expect(screen.getByText("Connectors")).toBeInTheDocument()
    expect(screen.getByText("Modules")).toBeInTheDocument()
    expect(screen.getByText("Billing · Credits")).toBeInTheDocument()
    // Governance (3)
    expect(screen.getByText("Audit trail")).toBeInTheDocument()
    expect(screen.getByText("Team · RBAC")).toBeInTheDocument()
    expect(screen.getByText("Compliance")).toBeInTheDocument()
  })
})
