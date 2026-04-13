"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Dashboard error:", error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-destructive/30 bg-destructive/5 p-10 text-center mx-4 my-8">
      <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
        <span className="text-destructive text-lg">!</span>
      </div>
      <div className="space-y-1">
        <p className="font-medium text-sm">Something went wrong</p>
        <p className="text-muted-foreground text-xs max-w-xs">
          {error.message ?? "An unexpected error occurred in this module."}
        </p>
        {error.digest ? (
          <p className="text-muted-foreground text-xs font-mono">Ref: {error.digest}</p>
        ) : null}
      </div>
      <Button variant="outline" size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}
