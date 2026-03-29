"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import type { CreditBalance as CreditBalanceType } from "@/types/billing"

interface CreditBalanceProps {
  balance: CreditBalanceType | null
  onTopUp: (credits: number) => Promise<void>
  isLoading: boolean
}

export function CreditBalance({ balance, onTopUp, isLoading }: CreditBalanceProps) {
  const [showTopUpModal, setShowTopUpModal] = useState(false)
  const [selectedCredits, setSelectedCredits] = useState<number>(100)
  const [customCredits, setCustomCredits] = useState<string>("")

  const usagePercent = useMemo(() => {
    if (!balance?.included_in_plan) {
      return 0
    }
    return Math.min(
      100,
      (balance.used_this_period / balance.included_in_plan) * 100,
    )
  }, [balance?.included_in_plan, balance?.used_this_period])

  const progressTone =
    usagePercent > 90
      ? "bg-[hsl(var(--brand-danger))]"
      : usagePercent >= 70
      ? "bg-[hsl(var(--brand-warning))]"
      : "bg-[hsl(var(--brand-success))]"

  const resolvedCredits =
    selectedCredits === -1
      ? Math.max(0, Number.parseInt(customCredits || "0", 10) || 0)
      : selectedCredits

  return (
    <>
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Current balance</p>
            <p className="text-3xl font-semibold text-foreground">
              {balance?.current_balance ?? 0}
            </p>
          </div>
          <Button type="button" onClick={() => setShowTopUpModal(true)}>
            Buy More Credits
          </Button>
        </div>
        <div className="mt-4">
          <div className="mb-2 flex justify-between text-xs text-muted-foreground">
            <span>Used this period</span>
            <span>
              {balance?.used_this_period ?? 0} / {balance?.included_in_plan ?? 0}
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted">
            <div
              className={`h-2 rounded-full ${progressTone}`}
              style={{ width: `${usagePercent}%` }}
            />
          </div>
          {balance?.expires_at ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Expires {new Date(balance.expires_at).toLocaleDateString()}
            </p>
          ) : null}
        </div>
      </section>

      {showTopUpModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-border bg-card p-5">
            <h4 className="text-lg font-semibold text-foreground">Top up credits</h4>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[100, 500, 1000, -1].map((credits) => (
                <button
                  key={credits}
                  type="button"
                  className={`rounded border px-3 py-2 text-sm ${
                    selectedCredits === credits
                      ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)] text-foreground"
                      : "border-border text-muted-foreground hover:bg-accent/30"
                  }`}
                  onClick={() => setSelectedCredits(credits)}
                >
                  {credits === -1 ? "Custom" : `${credits} Credits`}
                </button>
              ))}
            </div>
            {selectedCredits === -1 ? (
              <input
                className="mt-3 w-full rounded border border-border bg-background px-3 py-2 text-sm"
                placeholder="Enter credit amount"
                value={customCredits}
                onChange={(event) => setCustomCredits(event.target.value)}
              />
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowTopUpModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                disabled={resolvedCredits <= 0 || isLoading}
                onClick={() => {
                  void onTopUp(resolvedCredits).then(() => setShowTopUpModal(false))
                }}
              >
                {isLoading ? "Processing..." : "Confirm Top-up"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
