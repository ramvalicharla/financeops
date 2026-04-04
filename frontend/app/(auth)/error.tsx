"use client"

import Link from "next/link"

interface AuthErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function AuthError({ error, reset }: AuthErrorProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-sm">
        <h2 className="text-2xl font-semibold text-foreground">Unable to load this page</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The authentication page could not be loaded. Please try again.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            className="rounded-md bg-[hsl(var(--brand-primary))] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
            onClick={reset}
            type="button"
          >
            Try again
          </button>
          <Link
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition hover:bg-muted"
            href="/dashboard"
          >
            Go to dashboard
          </Link>
        </div>
        <p className="mt-6 text-xs text-muted-foreground">
          Reference: {error.digest ?? "Unavailable"}
        </p>
      </div>
    </div>
  )
}
