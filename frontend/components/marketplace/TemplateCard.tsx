"use client"

import Link from "next/link"
import type { MarketplaceTemplate } from "@/lib/types/marketplace"

interface TemplateCardProps {
  template: MarketplaceTemplate
}

export function TemplateCard({ template }: TemplateCardProps) {
  return (
    <Link
      href={`/marketplace/${template.id}`}
      className="block rounded-xl border border-border bg-card p-4 transition hover:border-[hsl(var(--brand-primary)/0.6)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{template.title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">{template.description}</p>
        </div>
        {template.is_featured ? (
          <span className="rounded-full border border-[hsl(var(--brand-primary)/0.45)] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-[hsl(var(--brand-primary))]">
            Featured
          </span>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded border border-border px-2 py-0.5">{template.template_type}</span>
        {template.industry ? <span className="rounded border border-border px-2 py-0.5">{template.industry}</span> : null}
        <span>{template.download_count} downloads</span>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">By {template.contributor?.display_name ?? "Contributor"}</span>
        <span className="text-sm font-semibold text-foreground">
          {template.is_free ? "FREE" : `${template.price_credits} credits`}
        </span>
      </div>
    </Link>
  )
}

