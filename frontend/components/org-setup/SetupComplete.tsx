"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import type { OrgSetupSummary } from "@/lib/api/orgSetup"

interface SetupCompleteProps {
  summary: OrgSetupSummary | undefined
  onEnter: () => void
}

export function SetupComplete({ summary, onEnter }: SetupCompleteProps) {
  const unmapped = summary?.mapping_summary.unmapped ?? 0
  const coaStatus = summary?.coa_status ?? "pending"
  const onboardingScore = summary?.onboarding_score ?? 0

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-6">
      <h2 className="text-2xl font-semibold text-foreground">Organisation setup complete</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm">
          <p className="text-muted-foreground">Group</p>
          <p className="font-medium text-foreground">{summary?.group?.group_name ?? "-"}</p>
        </div>
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm">
          <p className="text-muted-foreground">Entities configured</p>
          <p className="font-medium text-foreground">{summary?.entities.length ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm">
          <p className="text-muted-foreground">ERP tools configured</p>
          <p className="font-medium text-foreground">{summary?.erp_configs.length ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm">
          <p className="text-muted-foreground">Onboarding completeness</p>
          <p className="font-medium text-foreground">{onboardingScore}/100</p>
        </div>
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm">
          <p className="text-muted-foreground">CoA accounts initialised</p>
          <p className="font-medium text-foreground">{summary?.coa_account_count ?? 0}</p>
          {coaStatus !== "uploaded" ? (
            <p className="mt-1 text-xs text-muted-foreground">
              CoA status: {coaStatus.replace("_", " ")}. You can upload later from settings.
            </p>
          ) : null}
        </div>
        <div className="rounded-lg border border-border bg-background/40 p-3 text-sm md:col-span-2">
          <p className="text-muted-foreground">Mapping status</p>
          <p className="font-medium text-foreground">
            {summary?.mapping_summary.confirmed ?? 0} accounts confirmed
          </p>
          {unmapped > 0 ? (
            <p className="mt-1 text-xs text-amber-300">
              {unmapped} unmapped account(s). Resolve from{" "}
              <Link href="/settings/erp-mapping" className="underline">
                Settings -&gt; ERP Mapping
              </Link>
              .
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={onEnter}>Enter FinanceOps -&gt;</Button>
      </div>
    </section>
  )
}
