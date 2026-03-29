"use client"

import { CheckCircle2, Loader2, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ApplyTemplateResponse } from "@/lib/types/template-onboarding"

interface Step3ApplyProps {
  loading: boolean
  error: string | null
  result: ApplyTemplateResponse | null
  onRetry: () => void
  onContinue: () => void
}

export function Step3Apply({
  loading,
  error,
  result,
  onRetry,
  onContinue,
}: Step3ApplyProps) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Applying template</h2>
        <p className="text-sm text-muted-foreground">
          We are creating your board pack, reports, and default delivery schedule.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 rounded-md border border-border bg-card px-4 py-3 text-sm text-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Processing selected template...
        </div>
      ) : null}

      {error ? (
        <div className="space-y-3 rounded-md border border-destructive/40 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{error}</p>
          <Button type="button" variant="outline" onClick={onRetry}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Retry
          </Button>
        </div>
      ) : null}

      {result ? (
        <div className="space-y-2 rounded-md border border-border bg-card p-4">
          <div className="flex items-center gap-2 text-sm text-[hsl(var(--brand-success))]">
            <CheckCircle2 className="h-4 w-4" />
            Board pack definition created
          </div>
          <div className="flex items-center gap-2 text-sm text-[hsl(var(--brand-success))]">
            <CheckCircle2 className="h-4 w-4" />
            {result.report_definition_ids.length} report definitions created
          </div>
          <div className="flex items-center gap-2 text-sm text-[hsl(var(--brand-success))]">
            <CheckCircle2 className="h-4 w-4" />
            Delivery schedule created
          </div>
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button type="button" onClick={onContinue} disabled={!result || loading}>
          Continue
        </Button>
      </div>
    </section>
  )
}
