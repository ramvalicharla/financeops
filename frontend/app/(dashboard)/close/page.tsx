"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useSession } from "next-auth/react"
import {
  getPeriodStatus,
  lockPeriod,
  runReadiness,
  unlockPeriod,
} from "@/lib/api/close-governance"
import { useTenantStore } from "@/lib/store/tenant"
import { Button } from "@/components/ui/button"
import { LockReasonDialog } from "./_components/LockReasonDialog"

const toPeriodParts = (value: string): { fiscalYear: number; periodNumber: number } => {
  const [year, month] = value.split("-")
  const fiscalYear = Number.parseInt(year, 10)
  const periodNumber = Number.parseInt(month, 10)
  return {
    fiscalYear: Number.isFinite(fiscalYear) ? fiscalYear : new Date().getFullYear(),
    periodNumber: Number.isFinite(periodNumber) ? periodNumber : new Date().getMonth() + 1,
  }
}

const roleCanLock = (role: string): boolean =>
  ["finance_approver", "finance_leader", "super_admin", "platform_owner", "platform_admin"].includes(role)
const roleCanUnlock = (role: string): boolean =>
  ["finance_approver", "finance_leader", "super_admin", "platform_owner", "platform_admin"].includes(role)

type PendingDialogAction =
  | { action: "lock"; lockType: "SOFT_CLOSED" | "HARD_CLOSED" }
  | { action: "unlock" }
  | null

export default function ClosePage() {
  const searchParams = useSearchParams()
  const { data: session } = useSession()
  const userRole = String((session?.user as { role?: string } | undefined)?.role ?? "")
  const queryClient = useQueryClient()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const initialPeriod = searchParams?.get("period") ?? new Date().toISOString().slice(0, 7)
  const [period, setPeriod] = useState(initialPeriod)
  const [pendingDialogAction, setPendingDialogAction] = useState<PendingDialogAction>(null)
  const { fiscalYear, periodNumber } = useMemo(() => toPeriodParts(period), [period])

  const periodQuery = useQuery({
    queryKey: ["period-status", activeEntityId, fiscalYear, periodNumber],
    queryFn: async () =>
      getPeriodStatus({
        org_entity_id: activeEntityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
      }),
    enabled: Boolean(activeEntityId),
  })

  const readinessQuery = useQuery({
    queryKey: ["close-readiness", activeEntityId, fiscalYear, periodNumber],
    queryFn: async () =>
      runReadiness({
        org_entity_id: activeEntityId as string,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
      }),
    enabled: Boolean(activeEntityId),
  })

  const refresh = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["period-status"] })
    await queryClient.invalidateQueries({ queryKey: ["close-readiness"] })
  }

  const lockMutation = useMutation({
    mutationFn: ({
      lockType,
      reason,
    }: {
      lockType: "SOFT_CLOSED" | "HARD_CLOSED"
      reason: string
    }) => {
      return lockPeriod({
        org_entity_id: activeEntityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
        lock_type: lockType,
        reason,
      })
    },
    onSuccess: refresh,
  })

  const unlockMutation = useMutation({
    mutationFn: ({ reason }: { reason: string }) => {
      return unlockPeriod({
        org_entity_id: activeEntityId ?? undefined,
        fiscal_year: fiscalYear,
        period_number: periodNumber,
        reason,
      })
    },
    onSuccess: refresh,
  })

  const effectiveStatus = periodQuery.data?.status ?? "OPEN"

  const handleDialogConfirm = (reason: string) => {
    if (!pendingDialogAction) {
      return
    }

    const currentAction = pendingDialogAction
    setPendingDialogAction(null)

    if (currentAction.action === "lock") {
      lockMutation.mutate({ lockType: currentAction.lockType, reason })
      return
    }

    unlockMutation.mutate({ reason })
  }

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Period Close Control</h1>
          <p className="text-sm text-muted-foreground">
            Lock or unlock periods, review readiness, and manage close controls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            type="month"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
          />
          <Link href={`/close/checklist?period=${period}`}>
            <Button variant="outline">Open Checklist</Button>
          </Link>
        </div>
      </header>

      <section className="rounded-xl border border-border bg-card p-5">
        {!activeEntityId ? (
          <p className="text-sm text-muted-foreground">Select an active entity to manage period close.</p>
        ) : periodQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading period status...</p>
        ) : periodQuery.error ? (
          <p className="text-sm text-[hsl(var(--brand-danger))]">Failed to load period status.</p>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-md border border-border p-3">
                <p className="text-xs uppercase text-muted-foreground">Effective Status</p>
                <p className="mt-1 text-lg font-semibold text-foreground">{effectiveStatus}</p>
              </div>
              <div className="rounded-md border border-border p-3">
                <p className="text-xs uppercase text-muted-foreground">Locked At</p>
                <p className="mt-1 text-sm text-foreground">
                  {periodQuery.data?.locked_at ?? "-"}
                </p>
              </div>
              <div className="rounded-md border border-border p-3">
                <p className="text-xs uppercase text-muted-foreground">Reason</p>
                <p className="mt-1 text-sm text-foreground">
                  {periodQuery.data?.reason ?? "-"}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {roleCanLock(userRole) ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setPendingDialogAction({
                        action: "lock",
                        lockType: "SOFT_CLOSED",
                      })
                    }
                    disabled={lockMutation.isPending || !activeEntityId}
                  >
                    Soft Close
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() =>
                      setPendingDialogAction({
                        action: "lock",
                        lockType: "HARD_CLOSED",
                      })
                    }
                    disabled={lockMutation.isPending || !activeEntityId}
                  >
                    Hard Close
                  </Button>
                </>
              ) : null}
              {roleCanUnlock(userRole) ? (
                <Button
                  variant="outline"
                  onClick={() => setPendingDialogAction({ action: "unlock" })}
                  disabled={unlockMutation.isPending || !activeEntityId}
                >
                  Unlock
                </Button>
              ) : null}
            </div>
          </div>
        )}
      </section>

      <LockReasonDialog
        open={Boolean(pendingDialogAction)}
        action={pendingDialogAction?.action ?? "lock"}
        onConfirm={handleDialogConfirm}
        onCancel={() => setPendingDialogAction(null)}
      />

      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="text-base font-semibold text-foreground">Readiness</h2>
        {!activeEntityId ? (
          <p className="mt-2 text-sm text-muted-foreground">Select an entity to run readiness checks.</p>
        ) : readinessQuery.isLoading ? (
          <p className="mt-2 text-sm text-muted-foreground">Running readiness checks...</p>
        ) : readinessQuery.error ? (
          <p className="mt-2 text-sm text-[hsl(var(--brand-danger))]">Readiness check failed.</p>
        ) : (
          <div className="mt-3 space-y-3">
            <p className="text-sm text-foreground">
              Status:{" "}
              <span className={readinessQuery.data?.pass ? "text-emerald-400" : "text-amber-400"}>
                {readinessQuery.data?.pass ? "PASS" : "FAIL"}
              </span>
            </p>
            <div>
              <p className="text-sm font-medium text-foreground">Blockers</p>
              {readinessQuery.data?.blockers.length ? (
                <ul className="ml-5 list-disc text-sm text-[hsl(var(--brand-danger))]">
                  {readinessQuery.data.blockers.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No blockers.</p>
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">Warnings</p>
              {readinessQuery.data?.warnings.length ? (
                <ul className="ml-5 list-disc text-sm text-amber-300">
                  {readinessQuery.data.warnings.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No warnings.</p>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
