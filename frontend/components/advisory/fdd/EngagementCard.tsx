"use client"

import Link from "next/link"
import type { FDDEngagement } from "@/lib/types/fdd"

interface EngagementCardProps {
  engagement: FDDEngagement
}

export function EngagementCard({ engagement }: EngagementCardProps) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-foreground">{engagement.engagement_name}</h3>
          <p className="text-xs text-muted-foreground">{engagement.target_company_name}</p>
        </div>
        <span className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
          {engagement.status}
        </span>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Analysis: {engagement.analysis_period_start} to {engagement.analysis_period_end}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">Credit cost: {engagement.credit_cost.toLocaleString()} credits</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {engagement.sections_requested.map((section) => (
          <span
            key={`${engagement.id}-${section}`}
            className="rounded-md bg-[hsl(var(--brand-primary)/0.16)] px-2 py-1 text-[11px] text-foreground"
          >
            {section.replaceAll("_", " ")}
          </span>
        ))}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <Link href={`/advisory/fdd/${engagement.id}`} className="text-sm text-[hsl(var(--brand-primary))]">
          Open
        </Link>
        <Link href={`/advisory/fdd/${engagement.id}/report`} className="text-sm text-muted-foreground">
          Report
        </Link>
      </div>
    </article>
  )
}
