"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { completeOAuth } from "@/lib/api/sync"

export default function SyncConnectCallbackPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const connectionId = searchParams?.get("connection_id") ?? ""
    const state = searchParams?.get("state") ?? ""
    const code = searchParams?.get("code") ?? ""
    const realmId = searchParams?.get("realmId") ?? ""
    const organizationId =
      searchParams?.get("organization_id") ??
      searchParams?.get("organizationId") ??
      ""

    if (!connectionId || !state || !code) {
      setError("OAuth callback is missing required parameters.")
      return
    }

    let cancelled = false
    void completeOAuth(connectionId, {
      state,
      code,
      ...(realmId ? { realmId } : {}),
      ...(organizationId ? { organizationId } : {}),
    })
      .then(() => {
        if (cancelled) {
          return
        }
        router.replace(
          `/sync/connect?connection_id=${encodeURIComponent(connectionId)}&oauth=connected`,
        )
      })
      .catch((callbackError) => {
        if (cancelled) {
          return
        }
        setError(
          callbackError instanceof Error
            ? callbackError.message
            : "OAuth callback could not be completed.",
        )
      })

    return () => {
      cancelled = true
    }
  }, [router, searchParams])

  return (
    <section className="space-y-4 rounded-lg border border-border bg-card p-6">
      <h2 className="text-xl font-semibold text-foreground">Finishing ERP authorization</h2>
      {error ? (
        <div className="space-y-3">
          <p className="rounded-md border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] px-4 py-3 text-sm text-[hsl(var(--brand-danger))]">
            {error}
          </p>
          <Link className="text-sm font-medium text-[hsl(var(--brand-primary))]" href="/sync/connect">
            Return to connection setup
          </Link>
        </div>
      ) : (
        <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Validating OAuth callback and saving tokens...
        </p>
      )}
    </section>
  )
}
