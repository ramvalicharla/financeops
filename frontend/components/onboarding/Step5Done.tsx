"use client"

import Link from "next/link"
import { CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface Step5DoneProps {
  completionMessage: string | null
}

export function Step5Done({ completionMessage }: Step5DoneProps) {
  return (
    <section className="space-y-6">
      <div className="relative overflow-hidden rounded-xl border border-border bg-card p-6">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,_hsl(var(--brand-primary)/0.35),_transparent_55%)]" />
        <div className="relative space-y-2">
          <div className="inline-flex items-center gap-2 rounded-full border border-[hsl(var(--brand-success)/0.5)] bg-[hsl(var(--brand-success)/0.18)] px-3 py-1 text-xs text-[hsl(var(--brand-success))]">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Onboarding complete
          </div>
          <h2 className="text-2xl font-semibold text-foreground">You&apos;re all set!</h2>
          <p className="text-sm text-muted-foreground">
            Your workspace is configured with template defaults. Start exploring your outputs.
          </p>
          {completionMessage ? (
            <p className="text-xs text-muted-foreground">{completionMessage}</p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Link
          href="/board-pack"
          className="rounded-lg border border-border bg-card p-4 transition hover:border-[hsl(var(--brand-primary)/0.6)]"
        >
          <p className="font-medium text-foreground">View your board pack</p>
          <p className="text-sm text-muted-foreground">Open definitions and generate your first pack.</p>
        </Link>
        <Link
          href="/reports"
          className="rounded-lg border border-border bg-card p-4 transition hover:border-[hsl(var(--brand-primary)/0.6)]"
        >
          <p className="font-medium text-foreground">Explore reports</p>
          <p className="text-sm text-muted-foreground">Review template reports and adjust filters.</p>
        </Link>
      </div>

      <div className="flex justify-end">
        <Button asChild type="button">
          <Link href="/sync">Connect data now</Link>
        </Button>
      </div>
    </section>
  )
}
