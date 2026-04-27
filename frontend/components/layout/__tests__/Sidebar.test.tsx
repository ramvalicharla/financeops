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

// ── Tooltip mock — renders content always (no hover/focus required in tests) ─

vi.mock("@/components/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({
    children,
    asChild: _asChild,
  }: {
    children: React.ReactNode
    asChild?: boolean
  }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div role="tooltip">{children}</div>
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

// ── useOrgEntities mock ─────────────────────────────────────────────────────

vi.mock("@/hooks/useOrgEntities", () => ({
  useOrgEntities: vi.fn(),
}))

// ── Test helpers ────────────────────────────────────────────────────────────

import { useWorkspaceStore } from "@/lib/store/workspace"
import { useUIStore } from "@/lib/store/ui"
import { useTenantStore } from "@/lib/store/tenant"
import { useOrgEntities } from "@/hooks/useOrgEntities"

function mockStores({
  sidebarCollapsed = false,
  entityId = null as string | null,
} = {}) {
  const workspaceState = {
    sidebarCollapsed,
    sidebarOpen: false,
    entityId,
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

function mockEntities(
  entities: { entity_id: string; entity_name: string }[] = [],
) {
  ;(useOrgEntities as unknown as Mock).mockReturnValue({
    entities,
    isLoading: false,
    isError: false,
    error: null,
    isFromFallback: false,
  })
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
    mockEntities()
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

  // ── SP-4A new tests ─────────────────────────────────────────────────────

  it("renders sidebar at 52px when collapsed and 220px when expanded", () => {
    mockStores({ sidebarCollapsed: false })
    const { container, rerender } = render(<Sidebar {...defaultProps} />)
    const aside = container.querySelector("aside")
    expect(aside).toHaveStyle("width: 220px")

    mockStores({ sidebarCollapsed: true })
    rerender(<Sidebar {...defaultProps} />)
    expect(aside).toHaveStyle("width: 52px")
  })

  it("shows entity name in collapsed chip tooltip for single active entity", () => {
    mockStores({ sidebarCollapsed: true, entityId: "entity-001" })
    mockEntities([
      {
        entity_id: "entity-001",
        entity_name: "Acme Corp",
      },
    ])
    render(<Sidebar {...defaultProps} />)
    const tooltips = screen.getAllByRole("tooltip")
    const chipTooltip = tooltips.find((t) => t.textContent === "Acme Corp")
    expect(chipTooltip).toBeInTheDocument()
  })

  it("shows 'All entities' in collapsed chip tooltip when no entity is selected", () => {
    mockStores({ sidebarCollapsed: true, entityId: null })
    mockEntities([
      { entity_id: "entity-001", entity_name: "Acme Corp" },
      { entity_id: "entity-002", entity_name: "Beta Ltd" },
      { entity_id: "entity-003", entity_name: "Gamma Inc" },
    ])
    render(<Sidebar {...defaultProps} />)
    const tooltips = screen.getAllByRole("tooltip")
    const chipTooltip = tooltips.find((t) => t.textContent === "All entities")
    expect(chipTooltip).toBeInTheDocument()
  })

  it("shows name, 'Read-only access', and sign-out hint in avatar tooltip for tenant viewer", () => {
    mockStores({ sidebarCollapsed: true })
    render(
      <Sidebar
        {...defaultProps}
        userName="Alice Auditor"
        userRole={"auditor" as (typeof defaultProps)["userRole"]}
      />,
    )
    const tooltips = screen.getAllByRole("tooltip")
    const avatarTooltip = tooltips.find((t) => t.textContent?.includes("Read-only access"))
    expect(avatarTooltip).toBeInTheDocument()
    expect(avatarTooltip?.textContent).toContain("Alice Auditor")
    expect(avatarTooltip?.textContent).toContain("Click to sign out")
  })

  it("avatar aria-label includes user name and role rather than just 'Sign out'", () => {
    mockStores({ sidebarCollapsed: true })
    render(
      <Sidebar
        {...defaultProps}
        userName="Alice Auditor"
        userRole={"auditor" as (typeof defaultProps)["userRole"]}
      />,
    )
    const avatarButton = screen.getByRole("button", {
      name: /sign out.*alice auditor/i,
    })
    expect(avatarButton).toBeInTheDocument()
    expect(avatarButton).not.toHaveAccessibleName("Sign out")
    expect(avatarButton.getAttribute("aria-label")).toMatch(/read-only access/i)
  })
})
