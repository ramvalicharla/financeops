"use client"

import { Button } from "@/components/ui/button"
import type { OnboardingTemplateDetail } from "@/lib/types/template-onboarding"

interface Step2PreviewProps {
  template: OnboardingTemplateDetail | null
  loading: boolean
  error: string | null
  onBack: () => void
  onApply: () => void
}

export function Step2Preview({ template, loading, error, onBack, onApply }: Step2PreviewProps) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Template preview</h2>
        <p className="text-sm text-muted-foreground">
          Review what will be created before applying the template.
        </p>
      </div>

      {loading ? <div className="h-32 animate-pulse rounded-md bg-muted/40" /> : null}
      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      {template ? (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm font-medium text-foreground">Board pack sections</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {template.board_pack_sections.map((section, index) => (
                <li key={`${String(section["section_type"]) ?? "section"}-${index}`}>
                  {String(section["title"] ?? section["section_type"] ?? "Section")}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm font-medium text-foreground">Reports</p>
            <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
              {template.report_definitions.map((report, index) => (
                <li key={`${String(report["name"] ?? "report")}-${index}`}>
                  {String(report["name"] ?? "Report")}
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm font-medium text-foreground">Delivery schedule</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Cron: {String(template.delivery_schedule["cron_expression"] ?? "-")}
            </p>
            <p className="text-sm text-muted-foreground">
              Channel: {String(template.delivery_schedule["channel_type"] ?? "EMAIL")}
            </p>
          </div>
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" onClick={onApply} disabled={loading || !template}>
          Apply template
        </Button>
      </div>
    </section>
  )
}
