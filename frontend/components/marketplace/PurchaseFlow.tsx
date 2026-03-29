"use client"

import { useState } from "react"
import { purchaseMarketplaceTemplate } from "@/lib/api/marketplace"
import type { MarketplacePurchase } from "@/lib/types/marketplace"

interface PurchaseFlowProps {
  templateId: string
  priceCredits: number
  isFree: boolean
  onPurchased?: (purchase: MarketplacePurchase) => void
}

export function PurchaseFlow({ templateId, priceCredits, isFree, onPurchased }: PurchaseFlowProps) {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const handlePurchase = async () => {
    setLoading(true)
    setMessage(null)
    try {
      const payload = await purchaseMarketplaceTemplate(templateId)
      setMessage("Template unlocked. You can now apply it.")
      onPurchased?.(payload.purchase)
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Purchase failed"
      setMessage(detail)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm text-muted-foreground">Price</p>
      <p className="mt-1 text-xl font-semibold text-foreground">
        {isFree ? "FREE" : `${priceCredits} credits`}
      </p>
      <button
        type="button"
        onClick={() => void handlePurchase()}
        disabled={loading}
        className="mt-3 rounded-md border border-border px-3 py-2 text-sm text-foreground"
      >
        {loading ? "Processing..." : isFree ? "Get Free Template" : `Purchase for ${priceCredits} credits`}
      </button>
      {message ? <p className="mt-2 text-xs text-muted-foreground">{message}</p> : null}
    </section>
  )
}

