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
  current_org: string | null
  current_module: string | null
  current_period: string | null
  active_panel: ControlPlanePanel
  selected_intent_id: string | null
  selected_job_id: string | null
  selected_subject_type: string | null
  selected_subject_id: string | null
  intent_payload: IntentPanelState | null
  setCurrentOrg: (org: string | null) => void
  setCurrentModule: (module: string | null) => void
  setCurrentPeriod: (period: string | null) => void
  openIntentPanel: (payload: IntentPanelState) => void
  openJobPanel: (jobId?: string | null) => void
  openTimelinePanel: (subjectType?: string | null, subjectId?: string | null) => void
  openDeterminismPanel: (subjectType: string, subjectId: string) => void
  closePanel: () => void
}

export const useControlPlaneStore = create<ControlPlaneState>()(
  persist(
    (set) => ({
      current_org: null,
      current_module: null,
      current_period: null,
      active_panel: null,
      selected_intent_id: null,
      selected_job_id: null,
      selected_subject_type: null,
      selected_subject_id: null,
      intent_payload: null,
      setCurrentOrg: (org) => set({ current_org: org }),
      setCurrentModule: (module) => set({ current_module: module }),
      setCurrentPeriod: (period) => set({ current_period: period }),
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
      closePanel: () =>
        set({
          active_panel: null,
        }),
    }),
    {
      name: "financeops-control-plane-store",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        current_org: state.current_org,
        current_module: state.current_module,
        current_period: state.current_period,
        active_panel: state.active_panel,
        selected_intent_id: state.selected_intent_id,
        selected_job_id: state.selected_job_id,
        selected_subject_type: state.selected_subject_type,
        selected_subject_id: state.selected_subject_id,
        intent_payload: state.intent_payload,
      }),
    },
  ),
)
