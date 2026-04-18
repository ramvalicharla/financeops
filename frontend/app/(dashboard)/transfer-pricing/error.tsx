"use client"

import { useEffect } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ErrorBoundaryProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function TransferPricingErrorBoundary({ error, reset }: ErrorBoundaryProps) {
  useEffect(() => {
    // Log to error reporting (Sentry is already configured in the API client)
    console.error("[Transfer Pricing] Runtime error:", error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-5 p-8">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10">
        <AlertTriangle className="h-6 w-6 text-destructive" />
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Transfer Pricing encountered an error</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          Something went wrong loading this module. Your data is safe — this is an isolated view error.
        </p>
        {error.digest ? (
          <p className="font-mono text-xs text-muted-foreground">Error ID: {error.digest}</p>
        ) : null}
      </div>
      <Button onClick={reset} variant="outline" size="sm">
        <RefreshCw className="mr-2 h-3 w-3" /> Try again
      </Button>
    </div>
  )
}
