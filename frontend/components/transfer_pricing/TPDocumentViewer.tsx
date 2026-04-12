"use client"

import { StructuredDataView } from "@/components/ui"
import { type TransferPricingDoc } from "@/lib/types/sprint11"

export type TPDocumentViewerProps = {
  document: TransferPricingDoc
}

const renderSection = (label: string, value: unknown) => {
  if (value == null) {
    return null
  }
  return (
    <section key={label} className="rounded-md border border-border/60 p-3">
      <h3 className="text-sm font-semibold text-foreground">{label}</h3>
      <div className="mt-2">
        <StructuredDataView data={value} emptyMessage="No structured details are available." compact />
      </div>
    </section>
  )
}

export function TPDocumentViewer({ document }: TPDocumentViewerProps) {
  const content = document.content ?? {}
  const partA = content.part_a
  const partB = content.part_b
  const partC = content.part_c
  const partD = content.part_d

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">
        Form 3CEB - FY {document.fiscal_year} - v{document.version}
      </p>
      <div className="mt-3 space-y-3">
        {renderSection("Part A - General Information", partA)}
        {renderSection("Part B - International Transactions", partB)}
        {renderSection("Part C - Specified Domestic Transactions", partC)}
        {renderSection("Part D - Accountant Declaration", partD)}
      </div>
      {document.ai_narrative ? (
        <div className="mt-4 rounded-md border border-border/60 bg-background p-3">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">AI Narrative</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{document.ai_narrative}</p>
        </div>
      ) : null}
    </div>
  )
}
