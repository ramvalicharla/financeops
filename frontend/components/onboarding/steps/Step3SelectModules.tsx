"use client"

import { Button } from "@/components/ui/button"
import { FlowStrip, type FlowStripStep } from "@/components/ui/FlowStrip"
import type { ReviewRow, ModuleSelectionReview } from "@/lib/api/orgSetup"

interface ModuleRow {
  id: string
  module_name: string
  description?: string | null
  is_enabled: boolean
  health_status: string
  module_version: string
  route_prefix?: string | null
}

interface Step3Props {
  flowSteps: FlowStripStep[]
  modulesLoading: boolean
  modulesError: boolean
  modulesData: ModuleRow[] | undefined
  moduleReview: ModuleSelectionReview | null
  moduleReviewRows: ReviewRow[]
  enabledModuleNames: string[]
  onBack: () => void
  onNext: () => void
  onToggle: (moduleName: string, next: boolean) => void
  onReview: () => void
  isTogglingModule: boolean
  isReviewing: boolean
  renderQueryMessage: (state: { isLoading: boolean; isError: boolean; error: Error | null }, msg: string) => React.ReactNode
}

export function Step3SelectModules({
  flowSteps,
  modulesLoading,
  modulesError,
  modulesData,
  moduleReview,
  moduleReviewRows,
  enabledModuleNames,
  onBack,
  onNext,
  onToggle,
  onReview,
  isTogglingModule,
  isReviewing,
  renderQueryMessage,
}: Step3Props) {
  return (
    <section className="space-y-6 rounded-[2rem] border border-border bg-card p-6 shadow-sm">
      <FlowStrip
        title="Module Flow"
        subtitle="Choose which governed workspaces should be visible first. These switches call the backend registry."
        steps={flowSteps}
      />

      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Select Modules</h2>
        <p className="text-sm text-muted-foreground">
          Enable only the modules your team needs first. The shell reflects what the backend exposes.
        </p>
      </div>

      <section className="rounded-3xl border border-border bg-background/80 p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Backend review</p>
        <p className="mt-2 text-sm text-muted-foreground">
          This review is confirmed from backend state and does not replace the existing module enablement API.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {moduleReviewRows.map((row) => (
            <div key={row.label} className="rounded-2xl border border-border bg-card px-4 py-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{row.label}</p>
              <p className="mt-2 text-sm text-foreground">{row.value}</p>
            </div>
          ))}
        </div>
      </section>

      {modulesLoading || modulesError || !modulesData?.length
        ? renderQueryMessage(
            { isLoading: modulesLoading, isError: modulesError, error: null },
            "No modules are available yet. Start by enabling one governed workspace.",
          )
        : (
          <div className="grid gap-4 md:grid-cols-2">
            {modulesData.map((mod) => (
              <article key={mod.id} className="rounded-3xl border border-border bg-background/80 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <h3 className="text-base font-semibold text-foreground">{mod.module_name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {mod.description ?? "No description is available for this module yet."}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-medium ${
                      mod.is_enabled
                        ? "bg-[hsl(var(--brand-success)/0.14)] text-[hsl(var(--brand-success))]"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {mod.is_enabled ? "Enabled" : "Hidden"}
                  </span>
                </div>
                <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                  <span>Health: {mod.health_status}</span>
                  <span>Version: {mod.module_version}</span>
                </div>
                <div className="mt-5 flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">Route: {mod.route_prefix ?? "Not published"}</p>
                  <Button
                    variant={mod.is_enabled ? "outline" : "default"}
                    onClick={() => onToggle(mod.module_name, !mod.is_enabled)}
                    disabled={isTogglingModule}
                  >
                    {mod.is_enabled ? "Disable" : "Enable"}
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )
      }

      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" onClick={onBack}>← Back</Button>
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" onClick={onReview} disabled={isReviewing}>
            {isReviewing ? "Reviewing..." : "Review Backend Selection"}
          </Button>
          <Button type="button" onClick={onNext} disabled={!moduleReview && enabledModuleNames.length > 0}>
            Continue to Upload →
          </Button>
        </div>
      </div>
    </section>
  )
}
