"use client"

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  approvPublish,
  activateConnection,
  completeOAuth,
  createConnection,
  getConnection,
  getConnections,
  getDriftReport,
  getSyncRun,
  getSyncRuns,
  startOAuth,
  testConnection,
  triggerSync,
} from "@/lib/api/sync"
import { useAsyncAction, usePolling } from "@/hooks"
import type {
  CreateConnectionInput,
  OAuthCallbackResult,
  OAuthStartResult,
  TestConnectionResult,
} from "@/types/sync"

type SyncResourceKey =
  | "connections"
  | "sync-runs"
  | "sync-run"
  | "drift"

const resourceVersions: Record<SyncResourceKey, number> = {
  connections: 0,
  "sync-runs": 0,
  "sync-run": 0,
  drift: 0,
}

const listeners = new Map<SyncResourceKey, Set<() => void>>()

const subscribe = (key: SyncResourceKey, listener: () => void) => {
  const currentListeners = listeners.get(key) ?? new Set<() => void>()
  currentListeners.add(listener)
  listeners.set(key, currentListeners)

  return () => {
    currentListeners.delete(listener)
    if (!currentListeners.size) {
      listeners.delete(key)
    }
  }
}

const invalidate = (...keys: SyncResourceKey[]) => {
  for (const key of keys) {
    resourceVersions[key] += 1
    listeners.get(key)?.forEach((listener) => listener())
  }
}

const useResourceVersion = (key: SyncResourceKey) => {
  const [version, setVersion] = useState(resourceVersions[key])

  useEffect(() => subscribe(key, () => setVersion(resourceVersions[key])), [key])

  return version
}

export const useConnections = () => {
  const version = useResourceVersion("connections")
  const query = useQuery({
    queryKey: ["sync-connections", version],
    queryFn: getConnections,
  })

  return {
    data: query.data,
    error: query.error,
    isError: Boolean(query.error),
    isLoading: query.isLoading,
    refetch: query.refetch,
  }
}

export const useSyncRuns = (connectionId: string | null) => {
  const version = useResourceVersion("sync-runs")
  const query = useQuery({
    queryKey: ["sync-runs", connectionId, version],
    queryFn: () => getSyncRuns(connectionId ?? ""),
    enabled: Boolean(connectionId),
  })
  const hasActiveRun =
    query.data?.some(
      (run) => run.status === "RUNNING" || run.status === "PENDING",
    ) ?? false

  usePolling(
    async () => {
      if (!connectionId) {
        return
      }
      await query.refetch()
    },
    10_000,
    Boolean(connectionId) && hasActiveRun,
  )

  return {
    data: query.data,
    error: query.error,
    isError: Boolean(query.error),
    isLoading: query.isLoading,
    refetch: query.refetch,
  }
}

export const useSyncRun = (id: string | null) => {
  const version = useResourceVersion("sync-run")
  const query = useQuery({
    queryKey: ["sync-run", id, version],
    queryFn: () => getSyncRun(id ?? ""),
    enabled: Boolean(id),
  })

  return {
    data: query.data,
    error: query.error,
    isError: Boolean(query.error),
    isLoading: query.isLoading,
    refetch: query.refetch,
  }
}

export const useTriggerSync = () => {
  const mutation = useAsyncAction(async ({ connectionId }: { connectionId: string }) => {
    const result = await triggerSync(connectionId)
    invalidate("sync-runs", "connections")
    return result
  })

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}

export const useApprovePublish = () => {
  const mutation = useAsyncAction(async (publishEventId: string) => {
    const result = await approvPublish(publishEventId)
    invalidate("sync-runs")
    return result
  })

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}

export const useDriftReport = (syncRunId: string | null) => {
  const version = useResourceVersion("drift")
  const query = useQuery({
    queryKey: ["sync-drift", syncRunId, version],
    queryFn: () => getDriftReport(syncRunId ?? ""),
    enabled: Boolean(syncRunId),
  })

  return {
    data: query.data,
    error: query.error,
    isError: Boolean(query.error),
    isLoading: query.isLoading,
    refetch: query.refetch,
  }
}

export const useCreateConnection = () => {
  const mutation = useAsyncAction(async (payload: CreateConnectionInput) => {
    const result = await createConnection(payload)
    invalidate("connections")
    return result
  })

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}

export const useTestConnection = () => {
  const mutation = useAsyncAction(async (connectionId: string) =>
    testConnection(connectionId),
  )

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute as (connectionId: string) => Promise<TestConnectionResult>,
    reset: mutation.reset,
  }
}

export const useGetConnection = () => {
  const mutation = useAsyncAction(async (connectionId: string) => getConnection(connectionId))

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}

export const useStartOAuth = () => {
  const mutation = useAsyncAction(
    async ({
      connectionId,
      redirectUri,
    }: {
      connectionId: string
      redirectUri: string
    }) => startOAuth(connectionId, redirectUri),
  )

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute as (payload: {
      connectionId: string
      redirectUri: string
    }) => Promise<OAuthStartResult>,
    reset: mutation.reset,
  }
}

export const useCompleteOAuth = () => {
  const mutation = useAsyncAction(
    async ({
      connectionId,
      params,
    }: {
      connectionId: string
      params: Record<string, string>
    }) => completeOAuth(connectionId, params),
  )

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute as (payload: {
      connectionId: string
      params: Record<string, string>
    }) => Promise<OAuthCallbackResult>,
    reset: mutation.reset,
  }
}

export const useActivateConnection = () => {
  const mutation = useAsyncAction(async (connectionId: string) => {
    const result = await activateConnection(connectionId)
    invalidate("connections")
    return result
  })

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}
