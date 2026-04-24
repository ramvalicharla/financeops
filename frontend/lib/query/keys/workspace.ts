// Workspace shell — layout-level context queries (entity picker, tabs, sidebar data).
// Note: controlPlaneQueryKeys.* already factors the control-plane API calls that use
// structured param objects. These keys are the raw string arrays used by layout
// components that were NOT yet migrated to controlPlaneQueryKeys.

export const workspaceKeys = {
  // ["control-plane-context"] — entity-agnostic context (OnboardingWizard)
  context: () => ["control-plane-context"] as const,
  // ["control-plane-context", entityId] — entity-scoped context (Sidebar, ContextBar, Topbar)
  contextEntity: (entityId: string | null) =>
    ["control-plane-context", entityId] as const,
  // ["control-plane-context", entityId, "workspace-tabs"] — module tab list (ModuleTabs)
  tabs: (entityId: string | null) =>
    ["control-plane-context", entityId, "workspace-tabs"] as const,
  // ["control-plane-entities"] — list of all entities for the org (Sidebar)
  entities: () => ["control-plane-entities"] as const,
  // ["control-plane-airlock"] — airlock items summary (OnboardingWizard)
  airlock: () => ["control-plane-airlock"] as const,
  // ["active-entity", entityId] — full entity record for the currently active entity (useEntity hook)
  activeEntity: (entityId: string | null) =>
    ["active-entity", entityId] as const,
} as const
