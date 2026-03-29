"use client"

import { useDisplayScale } from "@/lib/store/displayScale"
import {
  formatAmount,
  formatPercent,
  formatRatio,
  SCALE_FULL_LABELS,
  type DisplayScale,
} from "@/lib/utils"

export function useFormattedAmount() {
  const { scale, currency } = useDisplayScale()

  return {
    scale,
    currency,

    fmt: (
      amount: number | string | null | undefined,
      overrideScale?: DisplayScale,
    ) => formatAmount(amount, overrideScale ?? scale, currency),

    fmtNum: (
      amount: number | string | null | undefined,
      overrideScale?: DisplayScale,
    ) =>
      formatAmount(amount, overrideScale ?? scale, currency, {
        showCurrency: false,
      }),

    fmtPct: formatPercent,
    fmtRatio: formatRatio,
    scaleLabel: SCALE_FULL_LABELS[scale],
  }
}
