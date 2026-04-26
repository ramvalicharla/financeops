// Data Sync — connections, sync runs, and drift detection.
// Cache invalidation is handled via queryClient.invalidateQueries (see useSync.ts).

export const syncKeys = {
  connections: () =>
    ["sync-connections"] as const,

  runs: (connectionId: string | null) =>
    ["sync-runs", connectionId] as const,

  // Prefix key for broad invalidation of all sync-runs regardless of connectionId.
  runsAll: () => ["sync-runs"] as const,

  run: (id: string | null) =>
    ["sync-run", id] as const,

  drift: (syncRunId: string | null) =>
    ["sync-drift", syncRunId] as const,
} as const
