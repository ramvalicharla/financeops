"use client"

import type { PPAIntangible } from "@/lib/types/ppa"
import { formatINR } from "@/lib/utils"

interface IntangibleCardProps {
  intangible: PPAIntangible
}

export function IntangibleCard({ intangible }: IntangibleCardProps) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-foreground">{intangible.intangible_name}</h4>
          <p className="text-xs text-muted-foreground">{intangible.intangible_category}</p>
        </div>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {intangible.valuation_method}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-muted-foreground">Fair value</dt>
          <dd className="text-foreground">{formatINR(intangible.fair_value)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Useful life</dt>
          <dd className="text-foreground">{intangible.useful_life_years} years</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Annual amortisation</dt>
          <dd className="text-foreground">{formatINR(intangible.annual_amortisation)}</dd>
        </div>
      </dl>
    </article>
  )
}
