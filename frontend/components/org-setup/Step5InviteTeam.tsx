"use client"

import { useState } from "react"
import { X, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { FormField } from "@/components/ui/FormField"

type InviteRole = "admin" | "member" | "viewer"

interface InviteRow {
  email: string
  role: InviteRole
}

interface Step5InviteTeamProps {
  onSkip: () => void
  onSubmit: (invites: InviteRow[]) => void
  submitting?: boolean
}

const ROLE_OPTIONS: Array<{ value: InviteRole; label: string }> = [
  { value: "admin", label: "Admin" },
  { value: "member", label: "Member" },
  { value: "viewer", label: "Viewer" },
]

const MAX_ROWS = 5

function defaultRow(): InviteRow {
  return { email: "", role: "member" }
}

export function Step5InviteTeam({ onSkip, onSubmit, submitting }: Step5InviteTeamProps) {
  const [rows, setRows] = useState<InviteRow[]>([defaultRow()])

  const updateRow = (index: number, field: keyof InviteRow, value: string) => {
    setRows((prev) =>
      prev.map((row, i) =>
        i === index ? { ...row, [field]: value } : row,
      ),
    )
  }

  const addRow = () => {
    if (rows.length < MAX_ROWS) {
      setRows((prev) => [...prev, defaultRow()])
    }
  }

  const removeRow = (index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const filled = rows.filter((row) => row.email.trim() !== "")
    onSubmit(filled)
  }

  return (
    <form
      className="space-y-4 rounded-xl border border-border bg-card p-5"
      onSubmit={handleSubmit}
    >
      <div>
        <h2 className="text-lg font-semibold text-foreground">Invite team</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Invite colleagues to collaborate. You can always do this later.
        </p>
      </div>

      <div className="space-y-2">
        {rows.map((row, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <div key={index} className="flex items-end gap-2">
            <div className="flex-1">
              <FormField
                id={`invite-email-${index}`}
                label={index === 0 ? "Email address" : ""}
              >
                <Input
                  id={`invite-email-${index}`}
                  type="email"
                  placeholder="colleague@company.com"
                  value={row.email}
                  onChange={(e) => updateRow(index, "email", e.target.value)}
                  autoComplete="off"
                />
              </FormField>
            </div>
            <div className="w-32">
              {index === 0 ? (
                <label
                  htmlFor={`invite-role-${index}`}
                  className="mb-1.5 block text-sm font-medium text-foreground"
                >
                  Role
                </label>
              ) : null}
              <select
                id={`invite-role-${index}`}
                value={row.role}
                onChange={(e) => updateRow(index, "role", e.target.value as InviteRole)}
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {ROLE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            {rows.length > 1 ? (
              <button
                type="button"
                aria-label="Remove invite"
                onClick={() => removeRow(index)}
                className="mb-0.5 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            ) : (
              <div className="w-9 shrink-0" />
            )}
          </div>
        ))}
      </div>

      {rows.length < MAX_ROWS ? (
        <button
          type="button"
          onClick={addRow}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <Plus className="h-4 w-4" />
          Add another
        </button>
      ) : null}

      <div className="flex items-center justify-between pt-1">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Skip for now
        </button>
        <Button type="submit" disabled={submitting}>
          Send invites &amp; finish
        </Button>
      </div>
    </form>
  )
}
