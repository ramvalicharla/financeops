import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { DeterminismPanel } from "@/components/panels/DeterminismPanel"
import { TimelinePanel } from "@/components/panels/TimelinePanel"
import { SnapshotNavigator } from "@/components/control-plane/SnapshotNavigator"
import { LineageView } from "@/components/control-plane/LineageView"
import { ImpactWarningModal } from "@/components/control-plane/ImpactWarningModal"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { useTenantStore } from "@/lib/store/tenant"

const listTimeline = vi.fn()
const getTimelineSemantics = vi.fn()
const exportTimeline = vi.fn()
const getDeterminism = vi.fn()
const getLineage = vi.fn()
const getImpact = vi.fn()
const listSnapshots = vi.fn()
const getSnapshot = vi.fn()
const compareSnapshots = vi.fn()
const createManualSnapshot = vi.fn()

vi.mock("@/lib/api/control-plane", () => ({
  listTimeline: (...args: unknown[]) => listTimeline(...args),
  getTimelineSemantics: (...args: unknown[]) => getTimelineSemantics(...args),
  exportTimeline: (...args: unknown[]) => exportTimeline(...args),
  getDeterminism: (...args: unknown[]) => getDeterminism(...args),
  getLineage: (...args: unknown[]) => getLineage(...args),
  getImpact: (...args: unknown[]) => getImpact(...args),
  listSnapshots: (...args: unknown[]) => listSnapshots(...args),
  getSnapshot: (...args: unknown[]) => getSnapshot(...args),
  compareSnapshots: (...args: unknown[]) => compareSnapshots(...args),
  createManualSnapshot: (...args: unknown[]) => createManualSnapshot(...args),
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
    getTimelineSemantics.mockResolvedValue({
      title: "Timeline",
      description: "Control-plane events returned by the backend timeline API.",
      empty_state: "No control-plane events in the current scope.",
      semantics: {
        authoritative: true,
        append_only_guarantee: false,
        compliance_grade: false,
        label_mode: "control_plane_events",
      },
      viewer_role: "finance_leader",
    })
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
    getLineage.mockResolvedValue({
      subject_type: "report_run",
      subject_id: "run-1",
      semantics: {
        authoritative: true,
        source: "backend_control_plane",
        mode: "run_graph",
      },
      forward: { nodes: [{ run_id: "run-1" }], edges: [] },
      reverse: { nodes: [{ subject_type: "board_pack_run" }], edges: [] },
    })
    getImpact.mockResolvedValue({
      subject_type: "report_run",
      subject_id: "run-1",
      semantics: {
        authoritative: true,
        source: "backend_control_plane",
        mode: "dependency_impact",
      },
      impacted_count: 2,
      impacted_reports_count: 1,
      warning: "This change affects 1 downstream reports.",
      impacted_nodes: [{ subject_type: "board_pack_run" }],
    })
  })

  it("renders the timeline panel from backend events", async () => {
    useControlPlaneStore.getState().openTimelinePanel("report_run", "run-1")

    renderWithProviders(<TimelinePanel />)

    expect(await screen.findByText("JOB_EXECUTED")).toBeInTheDocument()
    expect(screen.getByText("reports")).toBeInTheDocument()
    expect(screen.getByText(/control-plane events returned by the backend timeline api/i)).toBeInTheDocument()
  })

  it("changes timeline wording from backend semantics metadata", async () => {
    getTimelineSemantics.mockResolvedValueOnce({
      title: "Activity History",
      description: "Backend-defined activity history for the selected scope.",
      empty_state: "No activity history is available.",
      semantics: {
        authoritative: true,
        append_only_guarantee: false,
        compliance_grade: false,
        label_mode: "activity_history",
      },
      viewer_role: "finance_leader",
    })
    listTimeline.mockResolvedValueOnce([])
    useControlPlaneStore.getState().openTimelinePanel("report_run", "run-1")

    renderWithProviders(<TimelinePanel />)

    expect(await screen.findByText("Activity History")).toBeInTheDocument()
    expect(screen.getByText(/backend-defined activity history/i)).toBeInTheDocument()
    expect(screen.getByText(/no activity history is available/i)).toBeInTheDocument()
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

  it("renders backend-derived impact and lineage contracts", async () => {
    const user = userEvent.setup()
    renderWithProviders(<LineageView subjectType="report_run" subjectId="run-1" />)
    expect(await screen.findByText(/authoritative backend lineage/i)).toBeInTheDocument()

    renderWithProviders(
      <ImpactWarningModal open onClose={vi.fn()} subjectType="report_run" subjectId="run-1" />,
    )
    expect(await screen.findByText(/this change affects 1 downstream reports/i)).toBeInTheDocument()
    expect(screen.getByText(/authoritative backend impact/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /close dialog/i }))
  })
})
