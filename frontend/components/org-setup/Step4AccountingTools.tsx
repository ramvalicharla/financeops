"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { ERP_TYPE_OPTIONS } from "@/components/org-setup/constants"
import type { ErpConfigPayload, OrgEntity } from "@/lib/api/orgSetup"

interface Step4AccountingToolsProps {
  entities: OrgEntity[]
  submitting: boolean
  onSubmit: (configs: ErpConfigPayload[]) => Promise<void>
}

export function Step4AccountingTools({
  entities,
  submitting,
  onSubmit,
}: Step4AccountingToolsProps) {
  const [rows, setRows] = useState<ErpConfigPayload[]>(
    entities.map((entity) => ({
      org_entity_id: entity.id,
      erp_type: "MANUAL",
      erp_version: "",
      is_primary: true,
    })),
  )

  const optionsByValue = useMemo(() => {
    return new Map(ERP_TYPE_OPTIONS.map((option) => [option.value, option]))
  }, [])

  const updateRow = <K extends keyof ErpConfigPayload>(
    index: number,
    key: K,
    value: ErpConfigPayload[K],
  ) => {
    setRows((previous) => {
      const next = [...previous]
      next[index] = { ...next[index], [key]: value }
      return next
    })
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await onSubmit(
      rows.map((row) => ({
        ...row,
        erp_version: row.erp_version?.trim() || null,
      })),
    )
  }

  return (
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <h2 className="text-lg font-semibold text-foreground">Accounting tools</h2>
      <div className="space-y-3">
        {entities.map((entity, index) => {
          const selected = rows[index]
          const selectedOption = optionsByValue.get(selected?.erp_type)
          return (
            <div key={entity.id} className="grid gap-3 rounded-lg border border-border bg-background/40 p-4 md:grid-cols-4">
              <div className="text-sm text-foreground">{entity.display_name ?? entity.legal_name}</div>
              <select
                value={selected.erp_type}
                onChange={(event) => updateRow(index, "erp_type", event.target.value as ErpConfigPayload["erp_type"])}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                {ERP_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {selectedOption?.showVersion ? (
                <input
                  value={selected.erp_version ?? ""}
                  onChange={(event) => updateRow(index, "erp_version", event.target.value)}
                  placeholder="Version"
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                />
              ) : (
                <div className="text-sm text-muted-foreground">Version not required</div>
              )}
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  checked={selected.is_primary}
                  onChange={(event) => updateRow(index, "is_primary", event.target.checked)}
                  type="checkbox"
                />
                Primary
              </label>
            </div>
          )
        })}
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : "Continue"}
        </Button>
      </div>
    </form>
  )
}
