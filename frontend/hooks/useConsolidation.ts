"use client"

import { useQuery } from "@tanstack/react-query"
import {
  getConsolidationEntities,
  getConsolidationSummary,
  getFXRates,
} from "@/lib/api/consolidation"

export const useConsolidationEntities = (tenantId?: string) =>
  useQuery({
    queryKey: ["consolidation-entities", tenantId],
    queryFn: () => getConsolidationEntities(tenantId),
  })

export const useConsolidationSummary = (
  entityIds: string[],
  period: string | null,
) =>
  useQuery({
    queryKey: ["consolidation-summary", entityIds, period],
    queryFn: () => getConsolidationSummary(entityIds, period ?? ""),
    enabled: false,
  })

export const useFXRates = (period: string | null) =>
  useQuery({
    queryKey: ["consolidation-fx-rates", period],
    queryFn: () => getFXRates(period ?? ""),
    enabled: Boolean(period),
  })
