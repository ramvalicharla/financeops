// Data Sync — connections, sync runs, and drift detection.
// version is a cache-busting sentinel passed by the hook (incremented on manual refresh).

export const syncKeys = {
  connections: (version: number) =>
    ["sync-connections", version] as const,

  runs: (connectionId: string | null, version: number) =>
    ["sync-runs", connectionId, version] as const,

  run: (id: string | null, version: number) =>
    ["sync-run", id, version] as const,

  drift: (syncRunId: string | null, version: number) =>
    ["sync-drift", syncRunId, version] as const,
} as const
