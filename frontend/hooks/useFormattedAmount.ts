"use client"

import { useDisplayScale } from "@/lib/store/displayScale"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { useOrgEntities } from "@/hooks/useOrgEntities"
import {
  formatAmount,
  formatPercent,
  formatRatio,
  SCALE_FULL_LABELS,
  type DisplayScale,
} from "@/lib/utils"

export function useFormattedAmount() {
  const { scale, currency: displayCurrency } = useDisplayScale()
  const entityId = useWorkspaceStore((s) => s.entityId)
  const { entities } = useOrgEntities()

  const entityCurrency = entityId
    ? (entities.find((e) => e.entity_id === entityId)?.functional_currency ?? null)
    : null
  const effectiveCurrency = entityCurrency ?? displayCurrency

  return {
    scale,
    currency: effectiveCurrency,

    fmt: (
      amount: number | string | null | undefined,
      overrideScale?: DisplayScale,
    ) => formatAmount(amount, overrideScale ?? scale, effectiveCurrency),

    fmtNum: (
      amount: number | string | null | undefined,
      overrideScale?: DisplayScale,
    ) =>
      formatAmount(amount, overrideScale ?? scale, effectiveCurrency, {
        showCurrency: false,
      }),

    fmtPct: formatPercent,
    fmtRatio: formatRatio,
    scaleLabel: SCALE_FULL_LABELS[scale],
  }
}
