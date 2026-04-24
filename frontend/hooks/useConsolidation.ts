"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import {
  getConsolidationRun,
  getConsolidationRunStatements,
  getConsolidationSummary,
  getOrgSetupSummaryForConsolidation,
  runConsolidation,
} from "@/lib/api/consolidation"
import type { ConsolidationRunRequestPayload } from "@/types/consolidation"
import { queryKeys } from "@/lib/query/keys"

export const useOrgSetupSummaryForConsolidation = () =>
  useQuery({
    queryKey: queryKeys.orgSetup.summaryForConsolidation(),
    queryFn: getOrgSetupSummaryForConsolidation,
  })

export const useConsolidationSummary = (
  params: {
    orgGroupId: string
    asOfDate: string
    fromDate?: string
    toDate?: string
  } | null,
) =>
  useQuery({
    queryKey: queryKeys.consolidation.summary(params),
    queryFn: () =>
      getConsolidationSummary({
        orgGroupId: params?.orgGroupId ?? "",
        asOfDate: params?.asOfDate ?? "",
        fromDate: params?.fromDate,
        toDate: params?.toDate,
      }),
    enabled: Boolean(params?.orgGroupId && params?.asOfDate),
  })

export const useRunConsolidation = () =>
  useMutation({
    mutationFn: (payload: ConsolidationRunRequestPayload) =>
      runConsolidation(payload),
  })

export const useConsolidationRun = (runId: string | null) =>
  useQuery({
    queryKey: queryKeys.consolidation.run(runId),
    queryFn: () => getConsolidationRun(runId ?? ""),
    enabled: Boolean(runId),
  })

export const useConsolidationRunStatements = (runId: string | null) =>
  useQuery({
    queryKey: queryKeys.consolidation.runStatements(runId),
    queryFn: () => getConsolidationRunStatements(runId ?? ""),
    enabled: Boolean(runId),
  })
