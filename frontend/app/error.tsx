"use client"

interface GlobalErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-8 shadow-sm">
        <h2 className="text-2xl font-semibold text-foreground">Something went wrong</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          An unexpected problem interrupted this page. Please try again or reload the page.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-md bg-[hsl(var(--brand-primary))] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
            onClick={reset}
            type="button"
          >
            Try again
          </button>
          <button
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
            onClick={() => window.location.reload()}
            type="button"
          >
            Reload page
          </button>
        </div>
        <p className="mt-6 text-xs text-muted-foreground">
          Reference: {error.digest ?? "Unavailable"}
        </p>
      </div>
    </div>
  )
}
