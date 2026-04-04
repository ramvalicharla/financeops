"use client"

import { useEffect, useMemo, useState } from "react"
import {
  approvPublish,
  createConnection,
  getConnections,
  getDriftReport,
  getSyncRun,
  getSyncRuns,
  testConnection,
  triggerSync,
} from "@/lib/api/sync"
import { useAsyncAction, useFetch, usePolling } from "@/hooks"
import type {
  CreateConnectionInput,
  DatasetType,
  TestConnectionInput,
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
  const query = useFetch(getConnections, [version])

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
  const query = useFetch(
    () => getSyncRuns(connectionId ?? ""),
    [connectionId, version],
  )
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
  const query = useFetch(() => getSyncRun(id ?? ""), [id, version])

  return {
    data: query.data,
    error: query.error,
    isError: Boolean(query.error),
    isLoading: query.isLoading,
    refetch: query.refetch,
  }
}

export const useTriggerSync = () => {
  const mutation = useAsyncAction(
    async ({
      connectionId,
      datasetTypes,
    }: {
      connectionId: string
      datasetTypes: DatasetType[]
    }) => {
      const result = await triggerSync(connectionId, datasetTypes)
      invalidate("sync-runs", "connections")
      return result
    },
  )

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
  const query = useFetch(() => getDriftReport(syncRunId ?? ""), [syncRunId, version])

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
  const mutation = useAsyncAction(async (payload: TestConnectionInput) =>
    testConnection(payload),
  )

  return {
    error: mutation.error,
    isPending: mutation.isLoading,
    mutateAsync: mutation.execute,
    reset: mutation.reset,
  }
}

export const useAllDatasetTypes = () =>
  useMemo<DatasetType[]>(
    () => [
      "TRIAL_BALANCE",
      "GENERAL_LEDGER",
      "BANK_STATEMENT",
      "ACCOUNTS_RECEIVABLE",
      "ACCOUNTS_PAYABLE",
      "INVOICE_REGISTER",
      "PURCHASE_REGISTER",
      "PAYROLL_SUMMARY",
      "CHART_OF_ACCOUNTS",
      "VENDOR_MASTER",
      "CUSTOMER_MASTER",
      "GST_RETURN_GSTR1",
      "FIXED_ASSET_REGISTER",
    ],
    [],
  )
