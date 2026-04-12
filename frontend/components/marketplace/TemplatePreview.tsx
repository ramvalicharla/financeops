"use client"

import { StructuredDataView } from "@/components/ui"

interface TemplatePreviewProps {
  templateType: string
  templateData: Record<string, unknown>
}

const renderPreview = (templateType: string, templateData: Record<string, unknown>) => {
  if (templateType === "mis_template") {
    const lineItems = Array.isArray(templateData.line_items) ? templateData.line_items : []
    return (
      <ul className="space-y-1 text-sm text-muted-foreground">
        {lineItems.map((item, idx) => (
          <li key={`${String(item)}-${idx}`}>- {String(item)}</li>
        ))}
        {lineItems.length === 0 ? <li>No MIS line items in preview.</li> : null}
      </ul>
    )
  }

  if (templateType === "report_template") {
    const sections = Array.isArray(templateData.sections) ? templateData.sections : []
    return (
      <ul className="space-y-1 text-sm text-muted-foreground">
        {sections.map((section, idx) => (
          <li key={`${String(section)}-${idx}`}>Section {idx + 1}: {String(section)}</li>
        ))}
        {sections.length === 0 ? <li>No sections in preview.</li> : null}
      </ul>
    )
  }

  return (
    <StructuredDataView
      data={templateData}
      emptyMessage="No preview data is available for this template yet."
      compact
    />
  )
}

export function TemplatePreview({ templateType, templateData }: TemplatePreviewProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-foreground">Template Preview</h3>
      <div className="mt-3">{renderPreview(templateType, templateData)}</div>
    </section>
  )
}
