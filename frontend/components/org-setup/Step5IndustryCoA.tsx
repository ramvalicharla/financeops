"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { queryKeys } from "@/lib/query/keys"
import { Dialog } from "@/components/ui/Dialog"
import { getTemplateHierarchy, type CoaTemplate } from "@/lib/api/coa"
import type { OrgEntity } from "@/lib/api/orgSetup"

interface Step5IndustryCoAProps {
  entities: OrgEntity[]
  templates: CoaTemplate[]
  templatesLoading?: boolean
  templatesError?: boolean
  coaStatus?: "pending" | "uploaded" | "skipped" | "erp_connected"
  submitting: boolean
  skipping?: boolean
  onSubmit: (entityTemplates: Array<{ entity_id: string; template_id: string }>) => Promise<void>
  onSkip: () => Promise<void>
}

export function Step5IndustryCoA({
  entities,
  templates,
  templatesLoading = false,
  templatesError = false,
  coaStatus = "pending",
  submitting,
  skipping = false,
  onSubmit,
  onSkip,
}: Step5IndustryCoAProps) {
  const [selectedTemplateByEntity, setSelectedTemplateByEntity] = useState<Record<string, string>>({})
  const [previewTemplateId, setPreviewTemplateId] = useState<string | null>(null)

  const hierarchyQuery = useQuery({
    queryKey: queryKeys.orgSetup.templatePreview(previewTemplateId),
    queryFn: () => getTemplateHierarchy(previewTemplateId ?? ""),
    enabled: Boolean(previewTemplateId),
  })

  const canSubmit = useMemo(() => {
    return entities.length > 0 && entities.every((entity) => Boolean(selectedTemplateByEntity[entity.id]))
  }, [entities, selectedTemplateByEntity])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const payload = entities.map((entity) => ({
      entity_id: entity.id,
      template_id: selectedTemplateByEntity[entity.id] ?? "",
    }))
    await onSubmit(payload)
  }

  return (
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <h2 className="text-lg font-semibold text-foreground">Industry and chart of accounts</h2>
      <div className="space-y-1 text-sm text-muted-foreground">
        <p>Select an industry template to initialize later mapping and reporting defaults.</p>
        <p>You can upload later or connect your ERP.</p>
        <p>
          Current CoA status: <span className="font-semibold capitalize text-foreground">{coaStatus.replace("_", " ")}</span>
        </p>
      </div>
      {templatesError ? (
        <div className="rounded-lg border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-3 text-sm text-[hsl(var(--brand-danger))]">
          Failed to load chart of account templates. You can still skip this step for now.
        </div>
      ) : null}
      {templatesLoading ? (
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm text-muted-foreground">
          Loading industry templates...
        </div>
      ) : null}
      {!templatesLoading && !templatesError && templates.length === 0 ? (
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm text-muted-foreground">
          No industry templates are available right now. You can skip this step and continue onboarding.
        </div>
      ) : null}
      {entities.length === 0 ? (
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm text-muted-foreground">
          No legal entities were found for onboarding yet. Complete the earlier steps or skip this step for now.
        </div>
      ) : null}
      <div className="space-y-3">
        {entities.map((entity) => (
          <div key={entity.id} className="grid gap-3 rounded-lg border border-border bg-background/40 p-4 md:grid-cols-[1.4fr_1fr_auto]">
            <div className="text-sm text-foreground">{entity.display_name ?? entity.legal_name}</div>
            <select
              value={selectedTemplateByEntity[entity.id] ?? ""}
              onChange={(event) =>
                setSelectedTemplateByEntity((previous) => ({
                  ...previous,
                  [entity.id]: event.target.value,
                }))
              }
              disabled={templatesLoading || templatesError || templates.length === 0}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="">Select industry template</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                const selectedTemplate = selectedTemplateByEntity[entity.id]
                if (selectedTemplate) {
                  setPreviewTemplateId(selectedTemplate)
                }
              }}
              disabled={!selectedTemplateByEntity[entity.id]}
            >
              Preview
            </Button>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button type="button" variant="outline" onClick={() => void onSkip()} disabled={skipping}>
          {skipping ? "Skipping..." : "Skip for now"}
        </Button>
        <Button type="submit" disabled={!canSubmit || submitting}>
          {submitting ? "Initialising CoA..." : "Continue"}
        </Button>
      </div>

      {previewTemplateId ? (
        <Dialog open={Boolean(previewTemplateId)} onClose={() => setPreviewTemplateId(null)} title="Chart of accounts preview" size="lg">
          {hierarchyQuery.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, index) => (
                <div key={index} className="h-8 animate-pulse rounded-md bg-muted" />
              ))}
            </div>
          ) : hierarchyQuery.error ? (
            <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load template hierarchy.</p>
          ) : (
            <div className="space-y-3 text-sm">
              {hierarchyQuery.data?.classifications.map((classification) => (
                <div key={classification.id} className="rounded-lg border border-border p-3">
                  <p className="font-medium text-foreground">{classification.name}</p>
                  <ul className="mt-2 space-y-1 text-muted-foreground">
                    {classification.schedules.map((schedule) => (
                      <li key={schedule.id}>{schedule.name}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </Dialog>
      ) : null}
    </form>
  )
}
