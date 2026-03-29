"use client"

import { AllocationWaterfall } from "@/components/advisory/ppa/AllocationWaterfall"
import { IntangibleCard } from "@/components/advisory/ppa/IntangibleCard"
import type { PPAReport } from "@/lib/types/ppa"
import { formatINR } from "@/lib/utils"

interface PPAReportViewerProps {
  report: PPAReport
}

export function PPAReportViewer({ report }: PPAReportViewerProps) {
  return (
    <section className="space-y-4">
      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">Summary</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <div>
            <p className="text-xs text-muted-foreground">Purchase price</p>
            <p className="text-sm text-foreground">{formatINR(report.engagement.purchase_price)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Goodwill</p>
            <p className="text-sm text-foreground">{formatINR(report.allocation.goodwill)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Goodwill %</p>
            <p className="text-sm text-foreground">{report.goodwill_pct_of_purchase_price}%</p>
          </div>
        </div>
      </article>

      <AllocationWaterfall
        bookValueNetAssets={report.purchase_price_bridge.book_value_net_assets}
        totalIntangibles={report.allocation.total_intangibles_identified}
        deferredTaxLiability={report.allocation.deferred_tax_liability}
        goodwill={report.allocation.goodwill}
        purchasePrice={report.engagement.purchase_price}
      />

      <article className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-base font-semibold text-foreground">Amortisation Schedule</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 md:grid-cols-3">
          {Object.entries(report.amortisation_schedule).map(([year, value]) => (
            <div key={year} className="rounded-md border border-border/60 bg-background p-2">
              <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{year.replace("_", " ")}</p>
              <p className="text-sm text-foreground">{formatINR(value)}</p>
            </div>
          ))}
        </div>
      </article>

      <section className="grid gap-3 md:grid-cols-2">
        {report.intangibles.map((row) => (
          <IntangibleCard key={row.id} intangible={row} />
        ))}
      </section>
    </section>
  )
}
