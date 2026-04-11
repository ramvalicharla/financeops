import type { QueryKey } from "@tanstack/react-query"

interface ScopedListParams {
  entity_id?: string
  status?: string
  limit?: number
}

interface TimelineParams {
  entity_id?: string
  subject_type?: string
  subject_id?: string
  limit?: number
}

interface SnapshotParams {
  entity_id?: string
  subject_type?: string
  limit?: number
}

const withScope = (scope: {
  entity_id?: string
  status?: string
  limit?: number
  subject_type?: string
  subject_id?: string
}): Record<string, unknown> => ({
  entity_id: scope.entity_id ?? null,
  status: scope.status ?? null,
  limit: scope.limit ?? null,
  subject_type: scope.subject_type ?? null,
  subject_id: scope.subject_id ?? null,
})

export const controlPlaneQueryKeys = {
  entities: (): QueryKey => ["control-plane-entities"],
  entity: (entityId: string | null | undefined): QueryKey => ["control-plane-entity", entityId ?? null],
  context: (params?: { entity_id?: string; workspace?: string; module?: string }): QueryKey => [
    "control-plane-context",
    {
      entity_id: params?.entity_id ?? null,
      workspace: params?.workspace ?? null,
      module: params?.module ?? null,
    },
  ],
  intents: (params?: ScopedListParams): QueryKey => ["control-plane-intents", withScope(params ?? {})],
  intent: (intentId: string | null | undefined): QueryKey => ["control-plane-intent", intentId ?? null],
  jobs: (params?: ScopedListParams): QueryKey => ["control-plane-jobs", withScope(params ?? {})],
  airlockRoot: (): QueryKey => ["control-plane-airlock"],
  airlock: (params?: ScopedListParams): QueryKey => ["control-plane-airlock", withScope(params ?? {})],
  airlockItem: (itemId: string | null | undefined): QueryKey => ["control-plane-airlock-item", itemId ?? null],
  timeline: (params?: TimelineParams): QueryKey => ["control-plane-timeline", withScope(params ?? {})],
  timelineSemantics: (): QueryKey => ["control-plane-timeline-semantics"],
  determinism: (subjectType: string | null | undefined, subjectId: string | null | undefined): QueryKey => [
    "control-plane-determinism",
    subjectType ?? null,
    subjectId ?? null,
  ],
  lineage: (subjectType: string | null | undefined, subjectId: string | null | undefined): QueryKey => [
    "control-plane-lineage",
    subjectType ?? null,
    subjectId ?? null,
  ],
  impact: (subjectType: string | null | undefined, subjectId: string | null | undefined): QueryKey => [
    "control-plane-impact",
    subjectType ?? null,
    subjectId ?? null,
  ],
  snapshots: (params?: SnapshotParams): QueryKey => ["control-plane-snapshots", withScope(params ?? {})],
  snapshot: (snapshotId: string | null | undefined): QueryKey => ["control-plane-snapshot", snapshotId ?? null],
  snapshotCompare: (
    leftSnapshotId: string | null | undefined,
    rightSnapshotId: string | null | undefined,
  ): QueryKey => ["control-plane-snapshot-compare", leftSnapshotId ?? null, rightSnapshotId ?? null],
}
