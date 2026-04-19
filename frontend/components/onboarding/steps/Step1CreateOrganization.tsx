"use client"

import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import { Input } from "@/components/ui/input"
import { COUNTRY_OPTIONS, CURRENCY_OPTIONS } from "@/components/org-setup/constants"
import type { SetupIntentDraft, ReviewRow } from "@/lib/api/orgSetup"

interface Step1Props {
  flowSteps: FlowStripStep[]
  organizationName: string
  setOrganizationName: (v: string) => void
  organizationWebsite: string
  setOrganizationWebsite: (v: string) => void
  countryCode: string
  setCountryCode: (v: string) => void
  functionalCurrency: string
  setFunctionalCurrency: (v: string) => void
  reportingCurrency: string
  setReportingCurrency: (v: string) => void
  organizationDraft: SetupIntentDraft<"create_organization"> | null
  setOrganizationDraft: (d: null) => void
  organizationReviewRows: ReviewRow[]
  onSubmit: () => void
  isPendingDraft: boolean
  isPendingConfirm: boolean
}

export function Step1CreateOrganization({
  flowSteps,
  organizationName,
  setOrganizationName,
  organizationWebsite,
  setOrganizationWebsite,
  countryCode,
  setCountryCode,
  functionalCurrency,
  setFunctionalCurrency,
  reportingCurrency,
  setReportingCurrency,
  organizationDraft,
  setOrganizationDraft,
  organizationReviewRows,
  onSubmit,
  isPendingDraft,
  isPendingConfirm,
}: Step1Props) {
  return (
    <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
      <FlowStrip
        title="Workspace Flow"
        subtitle="Create the organization root before you add entities, modules, or data."
        steps={flowSteps}
      />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Create Organization</h2>
        <p className="text-sm text-muted-foreground">
          Start with the group-level identity that anchors entities, periods, and module context.
        </p>
      </div>

      <section className="rounded-3xl border border-border bg-background/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Review before submit</p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {organizationReviewRows.map((row) => (
            <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
              <p className="mt-2 text-sm text-foreground">{row.value}</p>
            </div>
          ))}
        </div>
      </section>

      <form
        className="grid gap-4 md:grid-cols-2"
        onSubmit={(e) => { e.preventDefault(); onSubmit() }}
      >
        <FormField id="organization-name" label="Organization legal name" required>
          <Input
            value={organizationName}
            onChange={(e) => { setOrganizationDraft(null); setOrganizationName(e.target.value) }}
            placeholder="Acme Holdings Pvt Ltd"
          />
        </FormField>

        <FormField id="organization-country" label="Country" required>
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={countryCode}
            onChange={(e) => { setOrganizationDraft(null); setCountryCode(e.target.value) }}
          >
            {COUNTRY_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </FormField>

        <FormField id="organization-functional-currency" label="Base currency" required>
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={functionalCurrency}
            onChange={(e) => { setOrganizationDraft(null); setFunctionalCurrency(e.target.value) }}
          >
            {CURRENCY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </FormField>

        <FormField id="organization-reporting-currency" label="Reporting currency" required>
          <select
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            value={reportingCurrency}
            onChange={(e) => { setOrganizationDraft(null); setReportingCurrency(e.target.value) }}
          >
            {CURRENCY_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </FormField>

        <div className="md:col-span-2">
          <FormField id="organization-website" label="Website">
            <Input
              value={organizationWebsite}
              onChange={(e) => { setOrganizationDraft(null); setOrganizationWebsite(e.target.value) }}
              placeholder="https://acme.example"
            />
          </FormField>
        </div>

        <div className="md:col-span-2 flex justify-end">
          <Button
            type="submit"
            disabled={isPendingDraft || isPendingConfirm || !organizationName.trim()}
          >
            {isPendingConfirm
              ? "Confirming..."
              : isPendingDraft
                ? "Preparing review..."
                : organizationDraft
                  ? "Confirm with Backend"
                  : "Review Before Submit"}
          </Button>
        </div>
      </form>
    </section>
  )
}
