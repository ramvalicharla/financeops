"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
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
import { queryKeys } from "@/lib/query/keys"
import { useAsyncAction, usePolling } from "@/hooks"
import type {
  CreateConnectionInput,
  OAuthCallbackResult,
  OAuthStartResult,
  TestConnectionResult,
} from "@/types/sync"

export const useConnections = () => {
  const query = useQuery({
    queryKey: queryKeys.sync.connections(),
    queryFn: getConnections,
    staleTime: 0,
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
  const query = useQuery({
    queryKey: queryKeys.sync.runs(connectionId),
    queryFn: () => getSyncRuns(connectionId ?? ""),
    enabled: Boolean(connectionId),
    staleTime: 0,
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
  const query = useQuery({
    queryKey: queryKeys.sync.run(id),
    queryFn: () => getSyncRun(id ?? ""),
    enabled: Boolean(id),
    staleTime: 0,
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
  const queryClient = useQueryClient()
  const mutation = useAsyncAction(async ({ connectionId }: { connectionId: string }) => {
    const result = await triggerSync(connectionId)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.sync.runsAll() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.sync.connections() }),
    ])
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
  const queryClient = useQueryClient()
  const mutation = useAsyncAction(async (publishEventId: string) => {
    const result = await approvPublish(publishEventId)
    await queryClient.invalidateQueries({ queryKey: queryKeys.sync.runsAll() })
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
  const query = useQuery({
    queryKey: queryKeys.sync.drift(syncRunId),
    queryFn: () => getDriftReport(syncRunId ?? ""),
    enabled: Boolean(syncRunId),
    staleTime: 0,
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
  const queryClient = useQueryClient()
  const mutation = useAsyncAction(async (payload: CreateConnectionInput) => {
    const result = await createConnection(payload)
    await queryClient.invalidateQueries({ queryKey: queryKeys.sync.connections() })
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
  const queryClient = useQueryClient()
  const mutation = useAsyncAction(async (connectionId: string) => {
    const result = await activateConnection(connectionId)
    await queryClient.invalidateQueries({ queryKey: queryKeys.sync.connections() })
    return result
  })

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}
