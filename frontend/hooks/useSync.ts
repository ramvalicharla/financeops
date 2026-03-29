"use client"

import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
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
import type { CreateConnectionInput, DatasetType, TestConnectionInput } from "@/types/sync"

export const useConnections = () =>
  useQuery({
    queryKey: ["connections"],
    queryFn: getConnections,
  })

export const useSyncRuns = (connectionId: string | null) =>
  useQuery({
    queryKey: ["sync-runs", connectionId],
    queryFn: () => getSyncRuns(connectionId ?? ""),
    enabled: Boolean(connectionId),
    refetchInterval: (query) => {
      const runs = query.state.data
      const hasActiveRun = runs?.some((run) =>
        run.status === "RUNNING" || run.status === "PENDING",
      )
      return hasActiveRun ? 10_000 : false
    },
  })

export const useSyncRun = (id: string | null) =>
  useQuery({
    queryKey: ["sync-run", id],
    queryFn: () => getSyncRun(id ?? ""),
    enabled: Boolean(id),
  })

export const useTriggerSync = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      connectionId,
      datasetTypes,
    }: {
      connectionId: string
      datasetTypes: DatasetType[]
    }) => triggerSync(connectionId, datasetTypes),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["sync-runs", variables.connectionId] })
      void queryClient.invalidateQueries({ queryKey: ["connections"] })
    },
  })
}

export const useApprovePublish = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (publishEventId: string) => approvPublish(publishEventId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sync-runs"] })
    },
  })
}

export const useDriftReport = (syncRunId: string | null) =>
  useQuery({
    queryKey: ["drift", syncRunId],
    queryFn: () => getDriftReport(syncRunId ?? ""),
    enabled: Boolean(syncRunId),
  })

export const useCreateConnection = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateConnectionInput) => createConnection(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["connections"] })
    },
  })
}

export const useTestConnection = () =>
  useMutation({
    mutationFn: (payload: TestConnectionInput) => testConnection(payload),
  })

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
