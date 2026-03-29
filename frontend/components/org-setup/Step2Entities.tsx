"use client"

import { useMemo, useState } from "react"
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

interface Step2EntitiesProps {
  submitting: boolean
  initial: Step2EntityPayload[]
  onSubmit: (entities: Step2EntityPayload[]) => Promise<void>
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

export function Step2Entities({ submitting, initial, onSubmit }: Step2EntitiesProps) {
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

  return (
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">Legal entities</h2>
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
              <Input
                placeholder="Legal name"
                value={row.legal_name}
                onChange={(event) => updateRow(index, "legal_name", event.target.value)}
                required
              />
              <Input
                placeholder="Display name"
                value={row.display_name ?? ""}
                onChange={(event) => updateRow(index, "display_name", event.target.value)}
              />
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
              {row.country_code === "IN" ? (
                <Input
                  placeholder="State code"
                  value={row.state_code ?? ""}
                  onChange={(event) => updateRow(index, "state_code", event.target.value)}
                />
              ) : null}
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
                <Input
                  placeholder="PAN"
                  value={row.pan ?? ""}
                  onChange={(event) => updateRow(index, "pan", event.target.value)}
                />
                <Input
                  placeholder="TAN"
                  value={row.tan ?? ""}
                  onChange={(event) => updateRow(index, "tan", event.target.value)}
                />
                <Input
                  placeholder="CIN"
                  value={row.cin ?? ""}
                  onChange={(event) => updateRow(index, "cin", event.target.value)}
                />
                <Input
                  placeholder="GSTIN"
                  value={row.gstin ?? ""}
                  onChange={(event) => updateRow(index, "gstin", event.target.value)}
                />
                <Input
                  placeholder="LEI"
                  value={row.lei ?? ""}
                  onChange={(event) => updateRow(index, "lei", event.target.value)}
                />
                <Input
                  placeholder="Incorporation no."
                  value={row.incorporation_number ?? ""}
                  onChange={(event) => updateRow(index, "incorporation_number", event.target.value)}
                />
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
  )
}
