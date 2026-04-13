"use client"

import { useMemo, useState } from "react"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  COUNTRY_OPTIONS,
  CURRENCY_OPTIONS,
  ENTITY_TYPE_OPTIONS,
  FISCAL_MONTHS,
  GAAP_OPTIONS,
} from "@/components/org-setup/constants"
import type { Step2EntityPayload } from "@/lib/api/orgSetup"
import { EntityTreePreview } from "@/components/org-setup/EntityTreePreview"

interface Step2EntitiesProps {
  submitting: boolean
  initial: Step2EntityPayload[]
  onSubmit: (entities: Step2EntityPayload[]) => Promise<void>
  orgName?: string
}

const defaultEntity = (): Step2EntityPayload => ({
  legal_name: "",
  display_name: "",
  entity_type: "WHOLLY_OWNED_SUBSIDIARY",
  country_code: "IN",
  state_code: "",
  functional_currency: "INR",
  reporting_currency: "INR",
  fiscal_year_start: 4,
  applicable_gaap: "INDAS",
  incorporation_number: "",
  pan: "",
  tan: "",
  cin: "",
  gstin: "",
  lei: "",
})

export function Step2Entities({ submitting, initial, onSubmit, orgName = "Your organisation" }: Step2EntitiesProps) {
  const [rows, setRows] = useState<Step2EntityPayload[]>(
    initial.length > 0 ? initial : [defaultEntity()],
  )
  const [showOptional, setShowOptional] = useState<Record<number, boolean>>({})

  const canSubmit = useMemo(
    () => rows.length > 0 && rows.every((row) => row.legal_name.trim().length > 0),
    [rows],
  )

  const updateRow = <K extends keyof Step2EntityPayload>(
    index: number,
    key: K,
    value: Step2EntityPayload[K],
  ) => {
    setRows((previous) => {
      const next = [...previous]
      next[index] = { ...next[index], [key]: value }
      return next
    })
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const payload = rows.map((row) => ({
      ...row,
      legal_name: row.legal_name.trim(),
      display_name: row.display_name?.trim() || null,
      state_code: row.country_code === "IN" ? row.state_code?.trim() || null : null,
      incorporation_number: row.incorporation_number?.trim() || null,
      pan: row.pan?.trim() || null,
      tan: row.tan?.trim() || null,
      cin: row.cin?.trim() || null,
      gstin: row.gstin?.trim() || null,
      lei: row.lei?.trim() || null,
    }))
    await onSubmit(payload)
  }

  const watchedEntities = rows.map((row, index) => ({
    id: String(index),
    name: row.legal_name,
    type: row.entity_type,
  }))

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_260px]">
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Entity structure</h2>
        <Button
          type="button"
          variant="outline"
          onClick={() => setRows((previous) => [...previous, defaultEntity()])}
        >
          Add entity
        </Button>
      </div>
      <div className="space-y-4">
        {rows.map((row, index) => (
          <div key={index} className="space-y-3 rounded-lg border border-border bg-background/40 p-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground">Entity {index + 1}</p>
              {rows.length > 1 ? (
                <button
                  type="button"
                  className="text-xs text-[hsl(var(--brand-danger))]"
                  onClick={() =>
                    setRows((previous) => previous.filter((_, rowIndex) => rowIndex !== index))
                  }
                >
                  Remove
                </button>
              ) : null}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <FormField id={`entity-legal-name-${index}`} label="Legal name" required>
                <Input
                  placeholder="Legal name"
                  value={row.legal_name}
                  onChange={(event) => updateRow(index, "legal_name", event.target.value)}
                  required
                />
              </FormField>
              <FormField id={`entity-short-name-${index}`} label="Short name">
                <Input
                  placeholder="Display name"
                  value={row.display_name ?? ""}
                  onChange={(event) => updateRow(index, "display_name", event.target.value)}
                />
              </FormField>
              <FormField id={`entity-type-${index}`} label="Entity type" required>
                <select
                  value={row.entity_type}
                  onChange={(event) => updateRow(index, "entity_type", event.target.value as Step2EntityPayload["entity_type"])}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {ENTITY_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id={`entity-country-${index}`} label="Country" required>
                <select
                  value={row.country_code}
                  onChange={(event) => updateRow(index, "country_code", event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {COUNTRY_OPTIONS.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.label}
                    </option>
                  ))}
                </select>
              </FormField>
              {row.country_code === "IN" ? (
                <FormField id={`entity-state-code-${index}`} label="State code">
                  <Input
                    placeholder="State code"
                    value={row.state_code ?? ""}
                    onChange={(event) => updateRow(index, "state_code", event.target.value)}
                  />
                </FormField>
              ) : null}
              <FormField id={`entity-currency-${index}`} label="Functional currency" required>
                <select
                  value={row.functional_currency}
                  onChange={(event) => updateRow(index, "functional_currency", event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {CURRENCY_OPTIONS.map((currency) => (
                    <option key={currency} value={currency}>
                      {currency}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id={`entity-reporting-currency-${index}`} label="Reporting currency" required>
                <select
                  value={row.reporting_currency}
                  onChange={(event) => updateRow(index, "reporting_currency", event.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {CURRENCY_OPTIONS.map((currency) => (
                    <option key={currency} value={currency}>
                      {currency}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id={`entity-fiscal-year-${index}`} label="Fiscal year start">
                <select
                  value={row.fiscal_year_start}
                  onChange={(event) => updateRow(index, "fiscal_year_start", Number(event.target.value))}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {FISCAL_MONTHS.map((month) => (
                    <option key={month.value} value={month.value}>
                      {month.label}
                    </option>
                  ))}
                </select>
              </FormField>
              <FormField id={`entity-gaap-${index}`} label="Applicable GAAP">
                <select
                  value={row.applicable_gaap}
                  onChange={(event) => updateRow(index, "applicable_gaap", event.target.value as Step2EntityPayload["applicable_gaap"])}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
                >
                  {GAAP_OPTIONS.map((gaap) => (
                    <option key={gaap} value={gaap}>
                      {gaap}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>
            <button
              type="button"
              className="text-xs text-muted-foreground underline"
              onClick={() => setShowOptional((previous) => ({ ...previous, [index]: !previous[index] }))}
            >
              {showOptional[index] ? "Hide optional fields" : "Show optional fields"}
            </button>
            {showOptional[index] ? (
              <div className="grid gap-3 md:grid-cols-3">
                <FormField id={`entity-pan-${index}`} label="PAN">
                  <Input
                    placeholder="PAN"
                    value={row.pan ?? ""}
                    onChange={(event) => updateRow(index, "pan", event.target.value)}
                  />
                </FormField>
                <FormField id={`entity-tan-${index}`} label="TAN">
                  <Input
                    placeholder="TAN"
                    value={row.tan ?? ""}
                    onChange={(event) => updateRow(index, "tan", event.target.value)}
                  />
                </FormField>
                <FormField id={`entity-cin-${index}`} label="CIN">
                  <Input
                    placeholder="CIN"
                    value={row.cin ?? ""}
                    onChange={(event) => updateRow(index, "cin", event.target.value)}
                  />
                </FormField>
                <FormField id={`entity-gstin-${index}`} label="GSTIN">
                  <Input
                    placeholder="GSTIN"
                    value={row.gstin ?? ""}
                    onChange={(event) => updateRow(index, "gstin", event.target.value)}
                  />
                </FormField>
                <FormField id={`entity-lei-${index}`} label="LEI">
                  <Input
                    placeholder="LEI"
                    value={row.lei ?? ""}
                    onChange={(event) => updateRow(index, "lei", event.target.value)}
                  />
                </FormField>
                <FormField id={`entity-registration-number-${index}`} label="Registration number">
                  <Input
                    placeholder="Incorporation no."
                    value={row.incorporation_number ?? ""}
                    onChange={(event) => updateRow(index, "incorporation_number", event.target.value)}
                  />
                </FormField>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={submitting || !canSubmit}>
          {submitting ? "Saving..." : "Continue"}
        </Button>
      </div>
    </form>
    <div className="hidden lg:block sticky top-6">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Structure preview
      </p>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <EntityTreePreview
          entities={watchedEntities}
          orgName={orgName}
        />
      </div>
    </div>
    </div>
  )
}
