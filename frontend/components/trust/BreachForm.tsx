"use client"

import { useState } from "react"

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

  const submit = async () => {
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
        <input
          type="number"
          min={0}
          value={values.affected_user_count}
          onChange={(event) =>
            setValues((current) => ({ ...current, affected_user_count: Number(event.target.value) }))
          }
          className="rounded-md border border-border bg-background px-2 py-2 text-sm"
          placeholder="Affected users"
        />
        <input
          type="datetime-local"
          value={values.discovered_at}
          onChange={(event) => setValues((current) => ({ ...current, discovered_at: event.target.value }))}
          className="rounded-md border border-border bg-background px-2 py-2 text-sm"
        />
      </div>
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
        className="mt-3 w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
        placeholder="Affected data types (comma separated)"
      />
      <textarea
        value={values.description}
        onChange={(event) => setValues((current) => ({ ...current, description: event.target.value }))}
        className="mt-3 min-h-24 w-full rounded-md border border-border bg-background px-2 py-2 text-sm"
        placeholder="Breach description"
      />
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

