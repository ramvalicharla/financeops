"use client"

import { useEffect } from "react"

interface BoardPackErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function BoardPackError({ error, reset }: BoardPackErrorProps) {
  useEffect(() => {
    console.error("Board pack error:", error)
  }, [error])
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-8 shadow-sm">
        <h2 className="text-2xl font-semibold text-foreground">Unable to load board packs</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Board-pack definitions or runs could not be loaded. Please try again.
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
