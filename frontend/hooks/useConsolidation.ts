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

export const useOrgSetupSummaryForConsolidation = () =>
  useQuery({
    queryKey: ["org-setup-summary-for-consolidation"],
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
    queryKey: ["consolidation-summary", params],
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
    queryKey: ["consolidation-run", runId],
    queryFn: () => getConsolidationRun(runId ?? ""),
    enabled: Boolean(runId),
  })

export const useConsolidationRunStatements = (runId: string | null) =>
  useQuery({
    queryKey: ["consolidation-run-statements", runId],
    queryFn: () => getConsolidationRunStatements(runId ?? ""),
    enabled: Boolean(runId),
  })
