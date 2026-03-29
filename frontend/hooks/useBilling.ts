"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  cancelSubscription,
  createTopUp,
  getCreditBalance,
  getCreditLedger,
  getCurrentSubscription,
  getInvoices,
  getPlans,
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
