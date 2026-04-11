"use client"

import { create } from "zustand"
import { createJSONStorage, persist } from "zustand/middleware"

export type ControlPlanePanel = "intent" | "jobs" | "timeline" | "determinism" | null

export interface IntentPanelState {
  intent_id: string
  status: string
  job_id?: string | null
  next_action?: string | null
  record_refs?: Record<string, unknown> | null
  guard_results?: Record<string, unknown> | null
}

interface ControlPlaneState {
  active_panel: ControlPlanePanel
  selected_intent_id: string | null
  selected_job_id: string | null
  selected_subject_type: string | null
  selected_subject_id: string | null
  evidence_drawer_open: boolean
  evidence_subject_type: string | null
  evidence_subject_id: string | null
  intent_payload: IntentPanelState | null
  openIntentPanel: (payload: IntentPanelState) => void
  openJobPanel: (jobId?: string | null) => void
  openTimelinePanel: (subjectType?: string | null, subjectId?: string | null) => void
  openDeterminismPanel: (subjectType: string, subjectId: string) => void
  openEvidenceDrawer: (subjectType: string, subjectId: string) => void
  closeEvidenceDrawer: () => void
  closePanel: () => void
}

export const useControlPlaneStore = create<ControlPlaneState>()(
  persist(
    (set) => ({
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      selected_subject_type: null,
      selected_subject_id: null,
      evidence_drawer_open: false,
      evidence_subject_type: null,
      evidence_subject_id: null,
      intent_payload: null,
      openIntentPanel: (payload) =>
        set({
          active_panel: "intent",
          selected_intent_id: payload.intent_id,
          selected_job_id: payload.job_id ?? null,
          selected_subject_type: "intent",
          selected_subject_id: payload.intent_id,
          intent_payload: payload,
        }),
      openJobPanel: (jobId) =>
        set({
          active_panel: "jobs",
          selected_job_id: jobId ?? null,
        }),
      openTimelinePanel: (subjectType, subjectId) =>
        set({
          active_panel: "timeline",
          selected_subject_type: subjectType ?? null,
          selected_subject_id: subjectId ?? null,
        }),
      openDeterminismPanel: (subjectType, subjectId) =>
        set({
          active_panel: "determinism",
          selected_subject_type: subjectType,
          selected_subject_id: subjectId,
        }),
      openEvidenceDrawer: (subjectType, subjectId) =>
        set({
          evidence_drawer_open: true,
          evidence_subject_type: subjectType,
          evidence_subject_id: subjectId,
        }),
      closeEvidenceDrawer: () =>
        set({
          evidence_drawer_open: false,
        }),
      closePanel: () =>
        set({
          active_panel: null,
        }),
    }),
    {
      name: "financeops-control-plane-store",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        active_panel: state.active_panel,
        selected_intent_id: state.selected_intent_id,
        selected_job_id: state.selected_job_id,
        selected_subject_type: state.selected_subject_type,
        selected_subject_id: state.selected_subject_id,
        evidence_drawer_open: state.evidence_drawer_open,
        evidence_subject_type: state.evidence_subject_type,
        evidence_subject_id: state.evidence_subject_id,
        intent_payload: state.intent_payload,
      }),
    },
  ),
)
