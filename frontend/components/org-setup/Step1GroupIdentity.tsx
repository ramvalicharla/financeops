"use client"

import { useMemo, useState } from "react"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { COUNTRY_OPTIONS, CURRENCY_OPTIONS } from "@/components/org-setup/constants"
import type { Step1Payload } from "@/lib/api/orgSetup"

interface Step1GroupIdentityProps {
  initial?: Partial<Step1Payload>
  submitting: boolean
  onSubmit: (payload: Step1Payload) => Promise<void>
}

export function Step1GroupIdentity({
  initial,
  submitting,
  onSubmit,
}: Step1GroupIdentityProps) {
  const [groupName, setGroupName] = useState(initial?.group_name ?? "")
  const [countryCode, setCountryCode] = useState(initial?.country_code ?? "IN")
  const [functionalCurrency, setFunctionalCurrency] = useState(
    initial?.functional_currency ?? "INR",
  )
  const [reportingCurrency, setReportingCurrency] = useState(
    initial?.reporting_currency ?? "INR",
  )
  const [website, setWebsite] = useState(initial?.website ?? "")

  const countryName = useMemo(() => {
    return COUNTRY_OPTIONS.find((country) => country.code === countryCode)?.label ?? "India"
  }, [countryCode])

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await onSubmit({
      group_name: groupName.trim(),
      country_of_incorp: countryName,
      country_code: countryCode,
      functional_currency: functionalCurrency,
      reporting_currency: reportingCurrency,
      website: website.trim() || null,
      logo_url: null,
    })
  }

  return (
    <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={handleSubmit}>
      <h2 className="text-lg font-semibold text-foreground">Org details</h2>
      <div className="grid gap-4 md:grid-cols-2">
        <FormField id="group-legal-name" label="Legal name" required>
          <Input value={groupName} onChange={(event) => setGroupName(event.target.value)} required />
        </FormField>
        <FormField id="group-country" label="Country of incorporation" required>
          <select
            value={countryCode}
            onChange={(event) => setCountryCode(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          >
            {COUNTRY_OPTIONS.map((country) => (
              <option key={country.code} value={country.code}>
                {country.label}
              </option>
            ))}
          </select>
        </FormField>
        <FormField id="group-currency" label="Functional currency" required>
          <select
            value={functionalCurrency}
            onChange={(event) => setFunctionalCurrency(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          >
            {CURRENCY_OPTIONS.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </FormField>
        <FormField id="group-reporting-currency" label="Reporting currency" required>
          <select
            value={reportingCurrency}
            onChange={(event) => setReportingCurrency(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground"
          >
            {CURRENCY_OPTIONS.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </FormField>
      </div>
      <FormField id="group-website" label="Website">
        <Input value={website} onChange={(event) => setWebsite(event.target.value)} placeholder="https://" />
      </FormField>
      <div className="flex justify-end">
        <Button disabled={submitting || !groupName.trim()} type="submit">
          {submitting ? "Saving..." : "Continue"}
        </Button>
      </div>
    </form>
  )
}
