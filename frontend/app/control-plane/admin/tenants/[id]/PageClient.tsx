"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2, XCircle, Clock, Repeat2, ExternalLink } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/ui/StatusBadge"
import { ConfirmDialog } from "@/components/ui/ConfirmDialog"
import {
  adminGetTenant,
  adminExtendTrial,
  adminActivateTenant,
  adminSuspendTenant,
  adminChangePlan,
  adminSwitchTenant,
} from "@/lib/api/admin"
import type { AdminTenantDetail } from "@/lib/types/admin"
import { useSession } from "next-auth/react"
import type { UserRole } from "@/lib/auth"

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right">{value}</span>
    </div>
  )
}

function SectionSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {[...Array(rows)].map((_, i) => (
        <div key={i} className="flex justify-between py-2 border-b border-border last:border-0">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
        </div>
      ))}
    </div>
  )
}

type ActionState = "idle" | "loading" | "success" | "error"

function useActionState() {
  const [state, setState] = useState<ActionState>("idle")
  const [message, setMessage] = useState<string | null>(null)

  const run = async (fn: () => Promise<void>) => {
    setState("loading")
    setMessage(null)
    try {
      await fn()
      setState("success")
    } catch (err: unknown) {
      setState("error")
      setMessage(err instanceof Error ? err.message : "Action failed")
    }
  }

  return { state, message, run, reset: () => { setState("idle"); setMessage(null) } }
}

export function AdminTenantDetailPageClient() {
  const params = useParams()
  const router = useRouter()
  const { data: session } = useSession()
  const tenantId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? ""

  const [detail, setDetail] = useState<AdminTenantDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [extendDays, setExtendDays] = useState(14)
  const [actionFeedback, setActionFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null)
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false)

  const action = useActionState()

  const userRole = (session?.user as { role?: UserRole } | undefined)?.role
  const isPlatformOwner = userRole === "platform_owner" || userRole === "super_admin"

  const load = () => {
    setLoading(true)
    setFetchError(null)
    adminGetTenant(tenantId)
      .then(setDetail)
      .catch((err: unknown) => setFetchError(err instanceof Error ? err.message : "Failed to load tenant"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (tenantId) load()
  }, [tenantId])

  const showFeedback = (type: "success" | "error", message: string) => {
    setActionFeedback({ type, message })
    setTimeout(() => setActionFeedback(null), 4000)
  }

  const handleExtendTrial = async () => {
    await action.run(async () => {
      await adminExtendTrial(tenantId, extendDays)
      showFeedback("success", `Trial extended by ${extendDays} days.`)
      load()
    })
  }

  const handleActivate = async () => {
    await action.run(async () => {
      await adminActivateTenant(tenantId)
      showFeedback("success", "Subscription activated.")
      load()
    })
  }

  const handleSuspendConfirm = async () => {
    setSuspendDialogOpen(false)
    await action.run(async () => {
      await adminSuspendTenant(tenantId)
      showFeedback("success", "Subscription suspended.")
      load()
    })
  }

  const handleSuspend = () => {
    setSuspendDialogOpen(true)
  }

  const handleSwitch = async () => {
    await action.run(async () => {
      const result = await adminSwitchTenant(tenantId)
      // Store the switch token and redirect into the org context
      if (typeof window !== "undefined") {
        sessionStorage.setItem("platform_switch_token", result.switch_token)
        sessionStorage.setItem("platform_switch_tenant_id", result.tenant_id)
        sessionStorage.setItem("platform_switch_tenant_name", result.tenant_name)
      }
      showFeedback("success", `Switching into ${result.tenant_name}…`)
      setTimeout(() => router.push("/dashboard"), 800)
    })
  }

  const sub = detail?.subscription
  const tenant = detail?.tenant

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon-sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          {loading ? (
            <Skeleton className="h-7 w-48" />
          ) : (
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-semibold truncate">{tenant?.name ?? "Tenant"}</h1>
              {tenant && <StatusBadge status={tenant.status} />}
            </div>
          )}
          {!loading && tenant && (
            <p className="text-xs text-muted-foreground mt-0.5">{tenant.slug} · {tenant.country}</p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Global feedback */}
      {actionFeedback && (
        <div
          className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${
            actionFeedback.type === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
              : "border-destructive/40 bg-destructive/10 text-destructive"
          }`}
        >
          {actionFeedback.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <AlertTriangle className="h-4 w-4 shrink-0" />
          )}
          {actionFeedback.message}
        </div>
      )}

      {fetchError && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {fetchError}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column: subscription + actions */}
        <div className="space-y-6 lg:col-span-2">
          {/* Subscription card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Subscription</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <SectionSkeleton rows={5} />
              ) : sub ? (
                <>
                  <DetailRow label="Plan ID" value={<span className="font-mono text-xs">{sub.plan_id}</span>} />
                  <DetailRow label="Status" value={<StatusBadge status={sub.status} />} />
                  <DetailRow label="Billing Cycle" value={sub.billing_cycle} />
                  <DetailRow
                    label="Trial End"
                    value={sub.trial_end_date ? formatDate(sub.trial_end_date) : "—"}
                  />
                  <DetailRow label="Period" value={`${formatDate(sub.current_period_start)} – ${formatDate(sub.current_period_end)}`} />
                </>
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">No subscription found.</p>
              )}
            </CardContent>
          </Card>

          {/* Actions card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {action.state === "error" && action.message && (
                <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  <XCircle className="h-3.5 w-3.5 shrink-0" />
                  {action.message}
                </div>
              )}

              {/* Extend trial */}
              <div className="flex flex-col gap-2 rounded-lg border border-border p-4">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-amber-400" />
                  <span className="text-sm font-medium">Extend Trial</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={extendDays}
                    onChange={(e) => setExtendDays(Number(e.target.value))}
                    className="w-20 h-8 rounded-md border border-input bg-background px-2 text-sm text-center tabular-nums"
                  />
                  <span className="text-xs text-muted-foreground">days</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleExtendTrial}
                    disabled={action.state === "loading" || !sub || sub.status !== "trialing"}
                  >
                    Extend
                  </Button>
                  {sub && sub.status !== "trialing" && (
                    <span className="text-xs text-muted-foreground">Not in trial</span>
                  )}
                </div>
              </div>

              {/* Activate / Suspend row */}
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleActivate}
                  disabled={action.state === "loading" || !sub || sub.status === "active"}
                  className="flex items-center gap-1.5"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  Activate
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={handleSuspend}
                  disabled={action.state === "loading" || !sub || sub.status === "suspended"}
                  className="flex items-center gap-1.5"
                >
                  <XCircle className="h-3.5 w-3.5" />
                  Suspend
                </Button>
              </div>

              {/* Switch into org (platform_owner only) */}
              {isPlatformOwner && (
                <div className="flex flex-col gap-1.5 rounded-lg border border-border p-4">
                  <div className="flex items-center gap-2">
                    <ExternalLink className="h-4 w-4 text-blue-400" />
                    <span className="text-sm font-medium">Switch into Org</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Issues a 15-minute scoped token to access this tenant&apos;s workspace. Platform owner only.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleSwitch}
                    disabled={action.state === "loading"}
                    className="self-start mt-1"
                  >
                    <Repeat2 className="h-3.5 w-3.5 mr-1.5" />
                    Switch
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent invoices */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recent Invoices</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <SectionSkeleton rows={3} />
              ) : !detail?.recent_invoices.length ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No invoices.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-xs text-muted-foreground">
                      <th className="pb-2 text-left font-medium">Date</th>
                      <th className="pb-2 text-left font-medium">Status</th>
                      <th className="pb-2 text-right font-medium">Amount</th>
                      <th className="pb-2 text-right font-medium">Due</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.recent_invoices.map((inv) => (
                      <tr key={inv.id} className="border-b border-border/50 last:border-0">
                        <td className="py-2 text-muted-foreground">{formatDate(inv.created_at)}</td>
                        <td className="py-2"><StatusBadge status={inv.status} /></td>
                        <td className="py-2 text-right tabular-nums">{inv.currency} {inv.total}</td>
                        <td className="py-2 text-right text-muted-foreground">{formatDate(inv.due_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column: credits */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Credits</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  <Skeleton className="h-10 w-28" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ) : (
                <>
                  <p className="text-3xl font-semibold tabular-nums">
                    {(detail?.credit_balance ?? 0).toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">Current balance</p>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Credit Ledger</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-3">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="flex justify-between">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-4 w-16" />
                    </div>
                  ))}
                </div>
              ) : !detail?.recent_credits.length ? (
                <p className="text-sm text-muted-foreground py-4 text-center">No transactions.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {detail.recent_credits.map((cr) => (
                    <li key={cr.id} className="py-2.5 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground capitalize">
                          {cr.transaction_type.replace(/_/g, " ")}
                        </span>
                        <span
                          className={`text-sm font-semibold tabular-nums ${
                            cr.credits_delta >= 0 ? "text-emerald-400" : "text-destructive"
                          }`}
                        >
                          {cr.credits_delta >= 0 ? "+" : ""}
                          {cr.credits_delta.toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">
                          Balance after: {cr.credits_balance_after.toLocaleString()}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(cr.created_at)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={suspendDialogOpen}
        title="Suspend tenant subscription"
        description="This tenant will lose access until reactivated. Continue?"
        confirmLabel="Suspend"
        variant="destructive"
        onConfirm={handleSuspendConfirm}
        onCancel={() => setSuspendDialogOpen(false)}
      />
    </div>
  )
}
