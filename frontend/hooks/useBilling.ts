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
import { queryKeys } from "@/lib/query/keys"

export const useCurrentSubscription = () =>
  useQuery({
    queryKey: queryKeys.billing.subscription(),
    queryFn: getCurrentSubscription,
  })

export const usePlans = () =>
  useQuery({
    queryKey: queryKeys.billing.plans(),
    queryFn: getPlans,
  })

export const useCreditBalance = () =>
  useQuery({
    queryKey: queryKeys.billing.creditBalance(),
    queryFn: getCreditBalance,
  })

export const useCreditLedger = () =>
  useQuery({
    queryKey: queryKeys.billing.creditLedger(),
    queryFn: getCreditLedger,
  })

export const useInvoices = () =>
  useQuery({
    queryKey: queryKeys.billing.invoices(),
    queryFn: getInvoices,
  })

export const useCurrentEntitlements = (options?: { enabled?: boolean }) =>
  useQuery({
    queryKey: queryKeys.billing.entitlements(),
    queryFn: getCurrentEntitlements,
    enabled: options?.enabled ?? true,
  })

export const useUsageAggregates = (params?: { period_start?: string; period_end?: string }) =>
  useQuery({
    queryKey: queryKeys.billing.usage(params?.period_start, params?.period_end),
    queryFn: () => getUsageAggregates(params),
  })

export const useTopUp = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (credits: number) => createTopUp(credits),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.creditBalance() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.creditLedger() })
    },
  })
}

export const useCancelSubscription = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: cancelSubscription,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.subscription() })
    },
  })
}

export const useUpgradeSubscription = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ planId, cycle }: { planId: string; cycle: BillingCycle }) =>
      upgradeSubscription(planId, cycle),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.subscription() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.plans() })
    },
  })
}

export const useRefreshEntitlements = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshEntitlements,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.entitlements() })
    },
  })
}

export const useRecordUsage = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: recordUsage,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.usageAll() })
    },
  })
}

export const useGenerateInvoice = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: generateInvoice,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.billing.invoices() })
    },
  })
}

export const useCheckoutSession = () =>
  useMutation({
    mutationFn: createCheckoutSession,
  })
