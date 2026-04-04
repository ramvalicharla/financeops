"use client"

interface ScheduledDeliveryErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function ScheduledDeliveryError({
  error,
  reset,
}: ScheduledDeliveryErrorProps) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-8 shadow-sm">
        <h2 className="text-2xl font-semibold text-foreground">Unable to load scheduled delivery</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Delivery schedules could not be loaded right now. Please try again.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-md bg-[hsl(var(--brand-primary))] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
            onClick={reset}
            type="button"
          >
            Try again
          </button>
        </div>
        <p className="mt-6 text-xs text-muted-foreground">
          Reference: {error.digest ?? "Unavailable"}
        </p>
      </div>
    </div>
  )
}
