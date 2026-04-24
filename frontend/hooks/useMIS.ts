"use client"

import { useQuery } from "@tanstack/react-query"
import { getMISDashboard, getMISPeriods } from "@/lib/api/mis"
import { queryKeys } from "@/lib/query/keys"

export const useMISDashboard = (entityId: string | null, period: string | null) =>
  useQuery({
    queryKey: queryKeys.mis.dashboard(entityId, period),
    queryFn: () => getMISDashboard(entityId ?? "", period ?? ""),
    enabled: Boolean(entityId && period),
  })

export const useMISPeriods = (entityId: string | null) =>
  useQuery({
    queryKey: queryKeys.mis.periods(entityId),
    queryFn: () => getMISPeriods(entityId ?? ""),
    enabled: Boolean(entityId),
  })
