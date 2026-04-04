"use client"

import { useState } from "react"
import { FormField } from "@/components/ui/FormField"

interface BreachFormValues {
  breach_type: string
  description: string
  affected_user_count: number
  affected_data_types: string[]
  discovered_at: string
  severity: "low" | "medium" | "high" | "critical"
}

interface BreachFormProps {
  onSubmit: (payload: BreachFormValues) => Promise<void>
}

export function BreachForm({ onSubmit }: BreachFormProps) {
  const [values, setValues] = useState<BreachFormValues>({
    breach_type: "other",
    description: "",
    affected_user_count: 0,
    affected_data_types: [],
    discovered_at: new Date().toISOString().slice(0, 16),
    severity: "low",
  })
  const [saving, setSaving] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<{
    breach_type?: string
    severity?: string
    affected_user_count?: string
    discovered_at?: string
    affected_data_types?: string
    description?: string
  }>({})

  const submit = async () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!values.breach_type) nextFieldErrors.breach_type = "Breach type is required."
    if (!values.severity) nextFieldErrors.severity = "Severity is required."
    if (!values.discovered_at) nextFieldErrors.discovered_at = "Date discovered is required."
    if (values.affected_user_count < 0) {
      nextFieldErrors.affected_user_count = "Number of affected individuals cannot be negative."
    }
    if (values.affected_data_types.length === 0) {
      nextFieldErrors.affected_data_types = "Types of personal data involved are required."
    }
    if (!values.description.trim()) {
      nextFieldErrors.description = "Incident description is required."
    }
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }

    setFieldErrors({})
    setSaving(true)
    try {
      await onSubmit({
        ...values,
        discovered_at: new Date(values.discovered_at).toISOString(),
      })
      setValues((current) => ({ ...current, description: "" }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 rounded-md border border-[hsl(var(--brand-warning)/0.5)] bg-[hsl(var(--brand-warning)/0.1)] px-3 py-2 text-xs text-[hsl(var(--brand-warning))]">
        High/Critical breaches must be reported to DPA within 72 hours.
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <FormField id="breach-type" label="Breach type" error={fieldErrors.breach_type} required>
          <select
            value={values.breach_type}
            onChange={(event) => setValues((current) => ({ ...current, breach_type: event.target.value }))}
            className="rounded-md border border-border bg-background px-2 py-2 text-sm"
          >
            {[
              "unauthorized_access",
              "data_loss",
              "ransomware",
              "accidental_disclosure",
              "other",
            ].map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </FormField>
        <FormField id="breach-severity" label="Severity" error={fieldErrors.severity} required>
          <select
            value={values.severity}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                severity: event.target.value as BreachFormValues["severity"],
              }))
            }
            className="rounded-md border border-border bg-background px-2 py-2 text-sm"
          >
            {(["low", "medium", "high", "critical"] as const).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </FormField>
        <FormField
          id="breach-affected-individuals"
          label="Number of affected individuals"
          hint="Enter 0 if unknown at time of reporting"
          error={fieldErrors.affected_user_count}
          required
        >
          <input
            type="number"
            min={0}
            inputMode="decimal"
            value={values.affected_user_count}
            onChange={(event) =>
              setValues((current) => ({ ...current, affected_user_count: Number(event.target.value) }))
            }
            className="rounded-md border border-border bg-background px-2 py-2 text-sm"
          />
        </FormField>
        <FormField id="breach-date-discovered" label="Date discovered" error={fieldErrors.discovered_at} required>
          <input
            type="datetime-local"
            value={values.discovered_at}
            onChange={(event) => setValues((current) => ({ ...current, discovered_at: event.target.value }))}
            className="rounded-md border border-border bg-background px-2 py-2 text-sm"
          />
        </FormField>
      </div>
      <div className="mt-3 space-y-3">
        <FormField
          id="breach-data-types"
          label="Types of personal data involved"
          error={fieldErrors.affected_data_types}
          required
        >
          <input
            type="text"
            value={values.affected_data_types.join(",")}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                affected_data_types: event.target.value
                  .split(",")
                  .map((part) => part.trim())
                  .filter((part) => part.length > 0),
              }))
            }
            className="w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
          />
        </FormField>
        <FormField
          id="breach-description"
          label="Incident description"
          hint="Provide a clear factual description of the breach"
          error={fieldErrors.description}
          required
        >
          <textarea
            value={values.description}
            onChange={(event) => setValues((current) => ({ ...current, description: event.target.value }))}
            className="min-h-24 w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
          />
        </FormField>
      </div>
      <button
        type="button"
        onClick={() => void submit()}
        disabled={saving || values.description.trim().length === 0}
        className="mt-3 rounded-md border border-border px-3 py-2 text-sm text-foreground"
      >
        {saving ? "Submitting..." : "Report Breach"}
      </button>
    </section>
  )
}
