import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { DeterminismPanel } from "@/components/panels/DeterminismPanel"
import { TimelinePanel } from "@/components/panels/TimelinePanel"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"
import { ImpactWarningModal } from "@/components/control-plane/ImpactWarningModal"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const listTimeline = vi.fn()
const exportTimeline = vi.fn()
const getDeterminism = vi.fn()
const listSnapshots = vi.fn()
const getSnapshot = vi.fn()
const compareSnapshots = vi.fn()
const createManualSnapshot = vi.fn()
const getImpact = vi.fn()

vi.mock("@/lib/api/control-plane", () => ({
  listTimeline: (...args: unknown[]) => listTimeline(...args),
  exportTimeline: (...args: unknown[]) => exportTimeline(...args),
  getDeterminism: (...args: unknown[]) => getDeterminism(...args),
  listSnapshots: (...args: unknown[]) => listSnapshots(...args),
  getSnapshot: (...args: unknown[]) => getSnapshot(...args),
  compareSnapshots: (...args: unknown[]) => compareSnapshots(...args),
  createManualSnapshot: (...args: unknown[]) => createManualSnapshot(...args),
  getImpact: (...args: unknown[]) => getImpact(...args),
}))

const renderWithProviders = (ui: ReactNode) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe("phase 4 control plane surfaces", () => {
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
      current_module: "Reports",
      current_period: "2026-04",
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      selected_subject_type: null,
      selected_subject_id: null,
      intent_payload: null,
    })
    listTimeline.mockResolvedValue([
      {
        timeline_type: "JOB_EXECUTED",
        occurred_at: "2026-04-09T10:00:00Z",
        subject_type: "report_run",
        subject_id: "run-1",
        module_key: "reports",
        payload: {},
      },
    ])
    exportTimeline.mockResolvedValue(new Blob(["{}"], { type: "application/json" }))
    getDeterminism.mockResolvedValue({
      snapshot_id: "snapshot-1",
      module_key: "reports",
      snapshot_kind: "report_output",
      subject_type: "report_run",
      subject_id: "run-1",
      entity_id: null,
      version_no: 2,
      determinism_hash: "abc123",
      replay_supported: true,
      trigger_event: "report_generation_complete",
      snapshot_at: "2026-04-09T10:00:00Z",
      payload: {},
      comparison_payload: {},
      replay: { matches: true },
      inputs: [],
    })
    listSnapshots.mockResolvedValue([
      {
        snapshot_id: "snapshot-1",
        module_key: "reports",
        snapshot_kind: "report_output",
        subject_type: "report_run",
        subject_id: "run-1",
        entity_id: null,
        version_no: 2,
        determinism_hash: "abc123456789",
        replay_supported: true,
        trigger_event: "report_generation_complete",
        snapshot_at: "2026-04-09T10:00:00Z",
        payload: {},
        comparison_payload: {},
      },
      {
        snapshot_id: "snapshot-0",
        module_key: "reports",
        snapshot_kind: "report_output",
        subject_type: "report_run",
        subject_id: "run-1",
        entity_id: null,
        version_no: 1,
        determinism_hash: "def987654321",
        replay_supported: true,
        trigger_event: "manual_snapshot",
        snapshot_at: "2026-04-08T10:00:00Z",
        payload: {},
        comparison_payload: {},
      },
    ])
    getSnapshot.mockResolvedValue({
      snapshot_id: "snapshot-1",
      module_key: "reports",
      snapshot_kind: "report_output",
      subject_type: "report_run",
      subject_id: "run-1",
      entity_id: null,
      version_no: 2,
      determinism_hash: "abc123456789",
      replay_supported: true,
      trigger_event: "report_generation_complete",
      snapshot_at: "2026-04-09T10:00:00Z",
      payload: {},
      comparison_payload: {},
      inputs: [],
    })
    compareSnapshots.mockResolvedValue({
      left_snapshot_id: "snapshot-1",
      right_snapshot_id: "snapshot-0",
      same_subject: true,
      same_hash: false,
      left_hash: "abc",
      right_hash: "def",
      left_version: 2,
      right_version: 1,
      comparison: { left: {}, right: {} },
    })
    createManualSnapshot.mockResolvedValue({
      snapshot_id: "snapshot-2",
      module_key: "reports",
      snapshot_kind: "report_output",
      subject_type: "report_run",
      subject_id: "run-1",
      entity_id: null,
      version_no: 3,
      determinism_hash: "ghi",
      replay_supported: true,
      trigger_event: "manual_snapshot",
      snapshot_at: "2026-04-09T11:00:00Z",
      payload: {},
      comparison_payload: {},
    })
    getImpact.mockResolvedValue({
      subject_type: "report_run",
      subject_id: "run-1",
      impacted_count: 3,
      impacted_reports_count: 2,
      warning: "This change affects 2 downstream reports.",
      impacted_nodes: [{ subject_type: "board_pack_run", subject_id: "bp-1" }],
    })
  })

  it("renders the timeline panel from backend events", async () => {
    useControlPlaneStore.getState().openTimelinePanel("report_run", "run-1")

    renderWithProviders(<TimelinePanel />)

    expect(await screen.findByText("JOB_EXECUTED")).toBeInTheDocument()
    expect(screen.getByText("reports")).toBeInTheDocument()
  })

  it("renders the determinism panel from backend evidence only", async () => {
    useControlPlaneStore.getState().openDeterminismPanel("report_run", "run-1")

    renderWithProviders(<DeterminismPanel />)

    expect(await screen.findByText("abc123")).toBeInTheDocument()
    expect(screen.getByText("report_generation_complete")).toBeInTheDocument()
  })

  it("loads snapshots and compares versions", async () => {
    renderWithProviders(<SnapshotNavigator />)

    expect(await screen.findByText("Snapshots")).toBeInTheDocument()
    await waitFor(() => expect(compareSnapshots).toHaveBeenCalled())
    expect(await screen.findByText("Hashes differ.")).toBeInTheDocument()
  })

  it("shows backend impact warning in modal", async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <ImpactWarningModal
        open
        onClose={vi.fn()}
        subjectType="report_run"
        subjectId="run-1"
      />,
    )

    expect(await screen.findByText("This change affects 2 downstream reports.")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /close dialog/i }))
  })
})
