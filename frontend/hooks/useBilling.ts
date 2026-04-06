"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  cancelSubscription,
  createCheckoutSession,
  createTopUp,
  generateInvoice,
  getCurrentEntitlements,
  getCreditBalance,
  getCreditLedger,
  getCurrentSubscription,
  getInvoices,
  getPlans,
  getUsageAggregates,
  refreshEntitlements,
  recordUsage,
  upgradeSubscription,
} from "@/lib/api/billing"
import type { BillingCycle } from "@/types/billing"

export const useCurrentSubscription = () =>
  useQuery({
    queryKey: ["billing-subscription"],
    queryFn: getCurrentSubscription,
  })

export const usePlans = () =>
  useQuery({
    queryKey: ["billing-plans"],
    queryFn: getPlans,
  })

export const useCreditBalance = () =>
  useQuery({
    queryKey: ["billing-credit-balance"],
    queryFn: getCreditBalance,
  })

export const useCreditLedger = () =>
  useQuery({
    queryKey: ["billing-credit-ledger"],
    queryFn: getCreditLedger,
  })

export const useInvoices = () =>
  useQuery({
    queryKey: ["billing-invoices"],
    queryFn: getInvoices,
  })

export const useCurrentEntitlements = (options?: { enabled?: boolean }) =>
  useQuery({
    queryKey: ["billing-entitlements"],
    queryFn: getCurrentEntitlements,
    enabled: options?.enabled ?? true,
  })

export const useUsageAggregates = (params?: { period_start?: string; period_end?: string }) =>
  useQuery({
    queryKey: ["billing-usage", params?.period_start, params?.period_end],
    queryFn: () => getUsageAggregates(params),
  })

export const useTopUp = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (credits: number) => createTopUp(credits),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-credit-balance"] })
      void queryClient.invalidateQueries({ queryKey: ["billing-credit-ledger"] })
    },
  })
}

export const useCancelSubscription = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cancelSubscription,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-subscription"] })
    },
  })
}

export const useUpgradeSubscription = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ planId, cycle }: { planId: string; cycle: BillingCycle }) =>
      upgradeSubscription(planId, cycle),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-subscription"] })
      void queryClient.invalidateQueries({ queryKey: ["billing-plans"] })
    },
  })
}

export const useRefreshEntitlements = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshEntitlements,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-entitlements"] })
    },
  })
}

export const useRecordUsage = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: recordUsage,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-usage"] })
    },
  })
}

export const useGenerateInvoice = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: generateInvoice,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing-invoices"] })
    },
  })
}

export const useCheckoutSession = () =>
  useMutation({
    mutationFn: createCheckoutSession,
  })
