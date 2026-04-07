"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import {
  getMarketplaceTemplate,
  rateMarketplaceTemplate,
} from "@/lib/api/marketplace"
import type {
  MarketplaceRating,
  MarketplaceTemplate,
} from "@/lib/types/marketplace"
import { TemplatePreview } from "@/components/marketplace/TemplatePreview"
import { PurchaseFlow } from "@/components/marketplace/PurchaseFlow"

export default function MarketplaceTemplateDetailPage() {
  const params = useParams()
  const templateId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""

  const [template, setTemplate] = useState<MarketplaceTemplate | null>(null)
  const [reviews, setReviews] = useState<MarketplaceRating[]>([])
  const [rating, setRating] = useState(5)
  const [reviewText, setReviewText] = useState("")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    if (!templateId) {
      return
    }
    setError(null)
    try {
      const payload = await getMarketplaceTemplate(templateId)
      setTemplate(payload.template)
      setReviews(payload.reviews)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load template")
    }
  }

  useEffect(() => {
    void load()
  }, [templateId])

  const submitRating = async () => {
    setMessage(null)
    setError(null)
    try {
      await rateMarketplaceTemplate(templateId, {
        rating,
        review_text: reviewText.trim() || undefined,
      })
      setMessage("Rating submitted.")
      setReviewText("")
      await load()
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Unable to submit rating")
    }
  }

  return (
    <div className="space-y-6">
      {template ? (
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">{template.title}</h1>
            <p className="text-sm text-muted-foreground">{template.description}</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
            {template.rating_average} stars ({template.rating_count} ratings)
          </div>
        </header>
      ) : (
        <header>
          <h1 className="text-2xl font-semibold text-foreground">Template Detail</h1>
        </header>
      )}

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}

      {template ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
          <div className="space-y-4">
            <TemplatePreview
              templateType={template.template_type}
              templateData={template.template_data}
            />

            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Contributor</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {template.contributor?.display_name ?? "Contributor"}
              </p>
              {template.contributor?.bio ? (
                <p className="mt-1 text-xs text-muted-foreground">{template.contributor.bio}</p>
              ) : null}
            </section>

            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Reviews</h2>
              <div className="mt-3 space-y-3">
                {reviews.map((row) => (
                  <article key={row.id} className="rounded-md border border-border bg-background p-3">
                    <p className="text-sm text-foreground">{row.rating} / 5</p>
                    <p className="mt-1 text-xs text-muted-foreground">{row.review_text ?? "No comment"}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">{row.created_at.slice(0, 10)}</p>
                  </article>
                ))}
                {reviews.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No reviews yet.</p>
                ) : null}
              </div>
            </section>
          </div>

          <div className="space-y-4">
            <PurchaseFlow
              templateId={template.id}
              priceCredits={template.price_credits}
              isFree={template.is_free}
            />
            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="text-sm font-semibold text-foreground">Rate this template</h2>
              <div className="mt-3 space-y-2">
                <select
                  value={rating}
                  onChange={(event) => setRating(Number(event.target.value))}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value={5}>5</option>
                  <option value={4}>4</option>
                  <option value={3}>3</option>
                  <option value={2}>2</option>
                  <option value={1}>1</option>
                </select>
                <textarea
                  value={reviewText}
                  onChange={(event) => setReviewText(event.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                  placeholder="Write a short review"
                />
                <button
                  type="button"
                  onClick={() => void submitRating()}
                  className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
                >
                  Submit Rating
                </button>
              </div>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  )
}
