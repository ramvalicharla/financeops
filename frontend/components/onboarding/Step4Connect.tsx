"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"

const erpProviders = [
  "Zoho Books",
  "Tally",
  "QuickBooks",
  "Xero",
  "SAP",
  "Oracle",
] as const

interface Step4ConnectProps {
  onSkip: () => void
  onConnected: () => void
}

export function Step4Connect({ onSkip, onConnected }: Step4ConnectProps) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-foreground">Connect your accounting software</h2>
        <p className="text-sm text-muted-foreground">
          Link your ERP to start real data sync and reconciliation.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {erpProviders.map((erp) => (
          <div key={erp} className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
            <div>
              <p className="text-sm font-medium text-foreground">{erp}</p>
              <p className="text-xs text-muted-foreground">Connector setup guidance</p>
            </div>
            <Button asChild type="button" variant="outline">
              <Link href={`/sync?erp=${encodeURIComponent(erp)}`}>Connect</Link>
            </Button>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" onClick={onSkip}>
          Skip for now
        </Button>
        <Button type="button" onClick={onConnected}>
          I&apos;ve connected
        </Button>
      </div>
    </section>
  )
}
