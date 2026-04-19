"use client"

import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { Input } from "@/components/ui/input"
import { COUNTRY_OPTIONS, CURRENCY_OPTIONS, GAAP_OPTIONS } from "@/components/org-setup/constants"
import type { SetupIntentDraft, ReviewRow, Step2EntityPayload, ApplicableGaap } from "@/lib/api/orgSetup"

const fiscalYearOptions = [
  { value: 1, label: "January" },
  { value: 4, label: "April" },
  { value: 7, label: "July" },
  { value: 10, label: "October" },
]

interface Step2Props {
  flowSteps: FlowStripStep[]
  entityPayload: Step2EntityPayload
  setEntityPayload: React.Dispatch<React.SetStateAction<Step2EntityPayload>>
  entityDraft: SetupIntentDraft<"create_entity"> | null
  setEntityDraft: (d: null) => void
  entityReviewRows: ReviewRow[]
  hasOrganization: boolean
  onBack: () => void
  onSubmit: () => void
  isPendingDraft: boolean
  isPendingConfirm: boolean
}

export function Step2CreateEntity({
  flowSteps,
  entityPayload,
  setEntityPayload,
  entityDraft,
  setEntityDraft,
  entityReviewRows,
  hasOrganization,
  onBack,
  onSubmit,
  isPendingDraft,
  isPendingConfirm,
}: Step2Props) {
  return (
    <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
      <FlowStrip
        title="Hierarchy Flow"
        subtitle="Create the first legal entity so the shell can anchor journals, periods, and governance."
        steps={flowSteps}
      />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Create Entity</h2>
        <p className="text-sm text-muted-foreground">
          Define the first operating entity so the workspace can show the right scope and framework.
        </p>
      </div>

      <section className="rounded-3xl border border-border bg-background/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {entityReviewRows.map((row) => (
            <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
              <p className="mt-2 text-sm text-foreground">{row.value}</p>
            </div>
          ))}
        </div>
      </section>

      {!hasOrganization ? (
        <div className="rounded-2xl border border-[hsl(var(--brand-warning)/0.4)] bg-[hsl(var(--brand-warning)/0.14)] p-4 text-sm text-foreground">
          No organization has been saved yet. Start with step 1 before creating an entity.
        </div>
      ) : (
        <form
          className="grid gap-4 md:grid-cols-2"
          onSubmit={(e) => { e.preventDefault(); onSubmit() }}
        >
          <FormField id="entity-legal-name" label="Entity legal name" required>
            <Input
              value={entityPayload.legal_name}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, legal_name: e.target.value } })}
              placeholder="Acme India Pvt Ltd"
            />
          </FormField>

          <FormField id="entity-display-name" label="Display name">
            <Input
              value={entityPayload.display_name ?? ""}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, display_name: e.target.value } })}
              placeholder="Acme India"
            />
          </FormField>

          <FormField id="entity-country" label="Country" required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={entityPayload.country_code}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, country_code: e.target.value } })}
            >
              {COUNTRY_OPTIONS.map((opt) => <option key={opt.code} value={opt.code}>{opt.label}</option>)}
            </select>
          </FormField>

          <FormField id="entity-functional-currency" label="Functional currency" required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={entityPayload.functional_currency}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, functional_currency: e.target.value } })}
            >
              {CURRENCY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </FormField>

          <FormField id="entity-reporting-currency" label="Reporting currency" required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={entityPayload.reporting_currency}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, reporting_currency: e.target.value } })}
            >
              {CURRENCY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </FormField>

          <FormField id="entity-fiscal-year" label="Fiscal year start" required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={entityPayload.fiscal_year_start}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, fiscal_year_start: Number(e.target.value) } })}
            >
              {fiscalYearOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
          </FormField>

          <FormField id="entity-gaap" label="Reporting framework" required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={entityPayload.applicable_gaap}
              onChange={(e) => setEntityPayload((cur) => { setEntityDraft(null); return { ...cur, applicable_gaap: e.target.value as ApplicableGaap } })}
            >
              {GAAP_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </FormField>

          <div className="md:col-span-2 flex items-center justify-between">
            <Button type="button" variant="outline" onClick={onBack}>
              ← Back
            </Button>
            <Button
              type="submit"
              disabled={isPendingDraft || isPendingConfirm || !entityPayload.legal_name.trim()}
            >
              {isPendingConfirm
                ? "Confirming..."
                : isPendingDraft
                  ? "Preparing review..."
                  : entityDraft
                    ? "Confirm with Backend"
                    : "Review Before Submit"}
            </Button>
          </div>
        </form>
      )}
    </section>
  )
}
