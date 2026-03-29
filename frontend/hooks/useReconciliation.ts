"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import {
  exportGLTBCSV,
  getGLTBAccountEntries,
  getGLTBResult,
  getPayrollCostCentreDetail,
  getPayrollRecon,
} from "@/lib/api/reconciliation"

export const useGLTBResult = (
  entityId: string | null,
  period: string | null,
  runId: string | null,
) =>
  useQuery({
    queryKey: ["gltb-result", entityId, period, runId],
    queryFn: () => getGLTBResult(entityId ?? "", period ?? "", runId ?? ""),
    enabled: Boolean(entityId && period && runId),
  })

export const useGLTBAccountEntries = (
  entityId: string | null,
  accountCode: string | null,
  period: string | null,
) =>
  useQuery({
    queryKey: ["gltb-account-entries", entityId, accountCode, period],
    queryFn: () =>
      getGLTBAccountEntries(entityId ?? "", accountCode ?? "", period ?? ""),
    enabled: Boolean(entityId && accountCode && period),
  })

export const useExportGLTB = () =>
  useMutation({
    mutationFn: ({
      entityId,
      period,
      runId,
    }: {
      entityId: string
      period: string
      runId: string
    }) => exportGLTBCSV(entityId, period, runId),
  })

export const usePayrollRecon = (
  entityId: string | null,
  period: string | null,
  runId: string | null,
) =>
  useQuery({
    queryKey: ["payroll-recon", entityId, period, runId],
    queryFn: () => getPayrollRecon(entityId ?? "", period ?? "", runId ?? ""),
    enabled: Boolean(entityId && period && runId),
  })

export const usePayrollCostCentreDetail = (
  entityId: string | null,
  costCentreId: string | null,
  period: string | null,
) =>
  useQuery({
    queryKey: ["payroll-cost-centre-detail", entityId, costCentreId, period],
    queryFn: () =>
      getPayrollCostCentreDetail(entityId ?? "", costCentreId ?? "", period ?? ""),
    enabled: Boolean(entityId && costCentreId && period),
  })
