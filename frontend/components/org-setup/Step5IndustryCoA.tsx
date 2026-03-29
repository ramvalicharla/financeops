"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { getTemplateHierarchy, type CoaTemplate } from "@/lib/api/coa"
import type { OrgEntity } from "@/lib/api/orgSetup"

interface Step5IndustryCoAProps {
  entities: OrgEntity[]
  templates: CoaTemplate[]
  submitting: boolean
  onSubmit: (entityTemplates: Array<{ entity_id: string; template_id: string }>) => Promise<void>
}

export function Step5IndustryCoA({
  entities,
  templates,
  submitting,
  onSubmit,
}: Step5IndustryCoAProps) {
  const [selectedTemplateByEntity, setSelectedTemplateByEntity] = useState<Record<string, string>>({})
  const [previewTemplateId, setPreviewTemplateId] = useState<string | null>(null)

  const hierarchyQuery = useQuery({
    queryKey: ["org-setup-template-preview", previewTemplateId],
    queryFn: () => getTemplateHierarchy(previewTemplateId ?? ""),
    enabled: Boolean(previewTemplateId),
  })

  const canSubmit = useMemo(() => {
    return entities.every((entity) => Boolean(selectedTemplateByEntity[entity.id]))
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
      <div className="flex justify-end">
        <Button type="submit" disabled={!canSubmit || submitting}>
          {submitting ? "Initialising CoA..." : "Continue"}
        </Button>
      </div>

      {previewTemplateId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="max-h-[80vh] w-full max-w-4xl overflow-auto rounded-xl border border-border bg-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-foreground">Template preview</h3>
              <Button type="button" variant="outline" onClick={() => setPreviewTemplateId(null)}>
                Close
              </Button>
            </div>
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
          </div>
        </div>
      ) : null}
    </form>
  )
}
