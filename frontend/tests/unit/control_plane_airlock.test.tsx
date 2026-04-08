import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AirlockQueue } from "@/components/airlock/AirlockQueue"
import { AirlockReview } from "@/components/airlock/AirlockReview"
import { useTenantStore } from "@/lib/store/tenant"

const listAirlockItems = vi.fn()
const getAirlockItem = vi.fn()
const admitAirlockItem = vi.fn()
const rejectAirlockItem = vi.fn()

vi.mock("@/lib/api/control-plane", () => ({
  listAirlockItems: (...args: unknown[]) => listAirlockItems(...args),
  getAirlockItem: (...args: unknown[]) => getAirlockItem(...args),
  admitAirlockItem: (...args: unknown[]) => admitAirlockItem(...args),
  rejectAirlockItem: (...args: unknown[]) => rejectAirlockItem(...args),
}))

const renderWithProviders = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("airlock ui", () => {
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
    listAirlockItems.mockResolvedValue([
      {
        airlock_item_id: "airlock-1",
        entity_id: "entity-1",
        source_type: "erp_sync_upload",
        source_reference: "conn-1",
        file_name: "sync.csv",
        mime_type: "text/csv",
        size_bytes: 120,
        checksum_sha256: "abc",
        status: "QUARANTINED",
        submitted_by_user_id: "user-1",
        reviewed_by_user_id: null,
        admitted_by_user_id: null,
        submitted_at: "2026-04-08T10:00:00Z",
        reviewed_at: null,
        admitted_at: null,
        rejected_at: null,
        rejection_reason: null,
        metadata: { source: "erp" },
        findings: [],
      },
    ])
    getAirlockItem.mockResolvedValue({
      airlock_item_id: "airlock-1",
      entity_id: "entity-1",
      source_type: "erp_sync_upload",
      source_reference: "conn-1",
      file_name: "sync.csv",
      mime_type: "text/csv",
      size_bytes: 120,
      checksum_sha256: "abc",
      status: "QUARANTINED",
      submitted_by_user_id: "user-1",
      reviewed_by_user_id: null,
      admitted_by_user_id: null,
      submitted_at: "2026-04-08T10:00:00Z",
      reviewed_at: null,
      admitted_at: null,
      rejected_at: null,
      rejection_reason: null,
      metadata: { source: "erp" },
      findings: [{ guard_code: "mime_valid", message: "PASS" }],
    })
    admitAirlockItem.mockResolvedValue({
      airlock_item_id: "airlock-1",
      status: "ADMITTED",
      admitted: true,
      checksum_sha256: "abc",
    })
    rejectAirlockItem.mockResolvedValue({
      airlock_item_id: "airlock-1",
      status: "REJECTED",
      admitted: false,
      checksum_sha256: "abc",
    })
  })

  it("loads queue items", async () => {
    renderWithProviders(<AirlockQueue />)

    expect(await screen.findByText("airlock-1")).toBeInTheDocument()
    expect(screen.getByText("erp_sync_upload")).toBeInTheDocument()
  })

  it("renders review findings and calls admit/reject backend hooks", async () => {
    const user = userEvent.setup()
    renderWithProviders(<AirlockReview itemId="airlock-1" />)

    expect(await screen.findByText(/mime_valid/i)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Admit" }))
    await waitFor(() => expect(admitAirlockItem).toHaveBeenCalledWith("airlock-1"))

    await user.type(screen.getByPlaceholderText(/optional reason/i), "needs correction")
    await user.click(screen.getByRole("button", { name: "Reject" }))
    await waitFor(() =>
      expect(rejectAirlockItem).toHaveBeenCalledWith("airlock-1", "needs correction"),
    )
  })
})
