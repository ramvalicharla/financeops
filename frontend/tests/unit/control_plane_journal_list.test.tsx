import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { JournalList } from "@/components/journals/JournalList"
import { useTenantStore } from "@/lib/store/tenant"

const listJournals = vi.fn()
const createGovernedIntent = vi.fn()

vi.mock("next-auth/react", () => ({
  useSession: () => ({
    data: {
      user: {
        role: "finance_leader",
      },
    },
  }),
}))

vi.mock("@/lib/api/accounting-journals", () => ({
  listJournals: (...args: unknown[]) => listJournals(...args),
}))

vi.mock("@/lib/api/intents", () => ({
  createGovernedIntent: (...args: unknown[]) => createGovernedIntent(...args),
}))

const renderWithProviders = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("journal control plane list", () => {
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
    listJournals.mockResolvedValue([
      {
        id: "journal-1",
        org_entity_id: "entity-1",
        journal_number: "JV-001",
        journal_date: "2026-04-08",
        reference: "REF-1",
        narration: "Payroll accrual",
        status: "APPROVED",
        posted_at: null,
        total_debit: "1200.00",
        total_credit: "1200.00",
        currency: "INR",
        created_by: "user-1",
        intent_id: "intent-1",
        job_id: "job-1",
        approval_status: "APPROVED",
        lines: [],
      },
    ])
  })

  it("renders journal rows with governed metadata", async () => {
    renderWithProviders(<JournalList />)

    expect(await screen.findByText("JV-001")).toBeInTheDocument()
    expect(screen.getAllByText("APPROVED").length).toBeGreaterThan(0)
    expect(screen.getByText("intent-1")).toBeInTheDocument()
    expect(screen.getByText("job-1")).toBeInTheDocument()
  })
})
