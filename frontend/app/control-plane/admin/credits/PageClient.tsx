"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  Filter,
  Search,
  Coins,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog } from "@/components/ui/Dialog"
import { ConfirmDialog } from "@/components/ui/ConfirmDialog"
import { adminListCredits, adminGrantCredits, adminGetTenant } from "@/lib/api/admin"
import type { AdminCreditRow, AdminCreditEntry } from "@/lib/types/admin"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null): string {
  if (!iso) return "—"
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

// ---------------------------------------------------------------------------
// Grant credits modal
// ---------------------------------------------------------------------------

type GrantTarget = { tenant_id: string; tenant_name: string; current_balance: number }

function GrantCreditsModal({
  open,
  target,
  onClose,
  onSuccess,
}: {
  open: boolean
  target: GrantTarget | null
  onClose: () => void
  onSuccess: () => void
}) {
  const [amount, setAmount] = useState(100)
  const [refId, setRefId] = useState("")
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setAmount(100)
      setRefId("")
      setApiError(null)
    }
  }, [open])

  const handleGrant = async () => {
    if (!target) return
    setSubmitting(true)
    setApiError(null)
    try {
      await adminGrantCredits({
        tenant_id: target.tenant_id,
        credits: amount,
        reference_id: refId.trim() || "platform_admin_grant",
      })
      setConfirmOpen(false)
      onSuccess()
      onClose()
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Failed to grant credits")
      setConfirmOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const isInvalid = amount <= 0 || isNaN(amount)

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title="Grant Credits"
        description={target ? `Granting credits to ${target.tenant_name}` : undefined}
        size="sm"
      >
        <div className="space-y-4">
          {apiError && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {apiError}
            </div>
          )}

          {target && (
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tenant</span>
                <span className="font-medium">{target.tenant_name}</span>
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-muted-foreground">Current Balance</span>
                <span className="tabular-nums font-medium">{target.current_balance.toLocaleString()}</span>
              </div>
            </div>
          )}

          <div>
            <label htmlFor="grant-amount" className="block text-xs font-medium text-muted-foreground mb-1">
              Credits to Grant *
            </label>
            <Input
              id="grant-amount"
              type="number"
              min="1"
              value={amount}
              onChange={(e) => setAmount(parseInt(e.target.value) || 0)}
              className="h-9"
            />
            {target && amount > 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                New balance: {(target.current_balance + amount).toLocaleString()}
              </p>
            )}
            {isInvalid && amount !== 0 && (
              <p className="mt-1 text-xs text-destructive">Amount must be greater than 0</p>
            )}
          </div>

          <div>
            <label htmlFor="grant-ref" className="block text-xs font-medium text-muted-foreground mb-1">
              Reference ID <span className="font-normal">(optional)</span>
            </label>
            <Input
              id="grant-ref"
              value={refId}
              onChange={(e) => setRefId(e.target.value)}
              placeholder="e.g. promo_q1_2026"
              className="h-9"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
            <Button variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button
              onClick={() => setConfirmOpen(true)}
              disabled={isInvalid || submitting}
            >
              <Coins className="h-3.5 w-3.5 mr-1.5" />
              Grant Credits
            </Button>
          </div>
        </div>
      </Dialog>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm Credit Grant"
        description={`Grant ${amount.toLocaleString()} credits to ${target?.tenant_name ?? "this tenant"}? This action is recorded in the audit log.`}
        confirmLabel="Confirm Grant"
        isLoading={submitting}
        onConfirm={handleGrant}
        onCancel={() => setConfirmOpen(false)}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Ledger modal
// ---------------------------------------------------------------------------

function LedgerModal({
  open,
  tenantId,
  tenantName,
  onClose,
}: {
  open: boolean
  tenantId: string | null
  tenantName: string
  onClose: () => void
}) {
  const [entries, setEntries] = useState<AdminCreditEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !tenantId) return
    setLoading(true)
    setError(null)
    adminGetTenant(tenantId)
      .then((detail) => setEntries(detail.recent_credits))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load ledger"))
      .finally(() => setLoading(false))
  }, [open, tenantId])

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={`Credit Ledger — ${tenantName}`}
      description="Last 10 transactions for this tenant."
      size="md"
    >
      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive mb-4">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex justify-between py-2 border-b border-border">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      ) : entries.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No transactions found.</p>
      ) : (
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th className="pb-2 text-left font-medium">Type</th>
                <th className="pb-2 text-right font-medium">Delta</th>
                <th className="pb-2 text-right font-medium">Balance After</th>
                <th className="pb-2 text-right font-medium">Date</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-b border-border/50 last:border-0">
                  <td className="py-2 text-muted-foreground capitalize">
                    {e.transaction_type.replace(/_/g, " ")}
                  </td>
                  <td className={`py-2 text-right tabular-nums font-medium ${
                    e.credits_delta >= 0 ? "text-emerald-400" : "text-destructive"
                  }`}>
                    {e.credits_delta >= 0 ? "+" : ""}{e.credits_delta.toLocaleString()}
                  </td>
                  <td className="py-2 text-right tabular-nums text-muted-foreground">
                    {e.credits_balance_after.toLocaleString()}
                  </td>
                  <td className="py-2 text-right text-muted-foreground whitespace-nowrap">
                    {formatDateTime(e.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Table skeleton
// ---------------------------------------------------------------------------

function TableSkeleton() {
  return (
    <>
      {[...Array(8)].map((_, i) => (
        <TableRow key={i}>
          <TableCell><Skeleton className="h-4 w-40" /></TableCell>
          <TableCell className="text-right"><Skeleton className="h-4 w-20 ml-auto" /></TableCell>
          <TableCell><Skeleton className="h-4 w-28" /></TableCell>
          <TableCell><Skeleton className="h-7 w-28 ml-auto" /></TableCell>
        </TableRow>
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type SortKey = "tenant_name" | "credit_balance" | "last_transaction_at"
type SortDir = "asc" | "desc"

export function AdminCreditsPageClient() {
  const [rows, setRows] = useState<AdminCreditRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null)

  const [query, setQuery] = useState("")
  const [lowBalanceOnly, setLowBalanceOnly] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>("credit_balance")
  const [sortDir, setSortDir] = useState<SortDir>("asc")

  const [grantTarget, setGrantTarget] = useState<GrantTarget | null>(null)
  const [grantOpen, setGrantOpen] = useState(false)

  const [ledgerTenantId, setLedgerTenantId] = useState<string | null>(null)
  const [ledgerTenantName, setLedgerTenantName] = useState("")
  const [ledgerOpen, setLedgerOpen] = useState(false)

  const showFeedback = (type: "success" | "error", msg: string) => {
    setFeedback({ type, msg })
    setTimeout(() => setFeedback(null), 4000)
  }

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    adminListCredits({ limit: 200, low_balance: lowBalanceOnly })
      .then((res) => setRows(res.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load credits"))
      .finally(() => setLoading(false))
  }, [lowBalanceOnly])

  useEffect(() => { load() }, [load])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => d === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir(key === "credit_balance" ? "asc" : "desc")
    }
  }

  const filtered = useMemo(() => {
    let list = rows
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter((r) => r.tenant_name.toLowerCase().includes(q))
    }
    return [...list].sort((a, b) => {
      let cmp = 0
      if (sortKey === "tenant_name") {
        cmp = a.tenant_name.localeCompare(b.tenant_name)
      } else if (sortKey === "credit_balance") {
        cmp = a.credit_balance - b.credit_balance
      } else {
        const ta = a.last_transaction_at ? new Date(a.last_transaction_at).getTime() : 0
        const tb = b.last_transaction_at ? new Date(b.last_transaction_at).getTime() : 0
        cmp = ta - tb
      }
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [rows, query, sortKey, sortDir])

  const lowCount = rows.filter((r) => r.credit_balance < 100).length

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return null
    return sortDir === "asc"
      ? <ChevronUp className="h-3 w-3 inline ml-0.5" />
      : <ChevronDown className="h-3 w-3 inline ml-0.5" />
  }

  const openGrant = (row: AdminCreditRow) => {
    setGrantTarget({
      tenant_id: row.tenant_id,
      tenant_name: row.tenant_name,
      current_balance: row.credit_balance,
    })
    setGrantOpen(true)
  }

  const openLedger = (row: AdminCreditRow) => {
    setLedgerTenantId(row.tenant_id)
    setLedgerTenantName(row.tenant_name)
    setLedgerOpen(true)
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold">Credits Management</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {loading
            ? "Loading…"
            : `${filtered.length} tenant${filtered.length !== 1 ? "s" : ""}${lowCount > 0 ? ` · ${lowCount} low balance` : ""}`}
        </p>
      </div>

      {/* Feedback */}
      {feedback && (
        <div
          className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${
            feedback.type === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
              : "border-destructive/40 bg-destructive/10 text-destructive"
          }`}
        >
          {feedback.type === "success"
            ? <CheckCircle2 className="h-4 w-4 shrink-0" />
            : <AlertTriangle className="h-4 w-4 shrink-0" />}
          {feedback.msg}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tenant…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
          <button
            onClick={() => setLowBalanceOnly((v) => !v)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              lowBalanceOnly
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            Low Balance (&lt;100)
            {lowCount > 0 && !lowBalanceOnly && (
              <span className="ml-1.5 rounded-full bg-amber-500/20 text-amber-300 px-1.5 py-0.5 text-[10px]">
                {lowCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead
                  className="pl-4 cursor-pointer select-none hover:text-foreground"
                  onClick={() => toggleSort("tenant_name")}
                >
                  Tenant <SortIcon col="tenant_name" />
                </TableHead>
                <TableHead
                  className="text-right cursor-pointer select-none hover:text-foreground"
                  onClick={() => toggleSort("credit_balance")}
                >
                  Balance <SortIcon col="credit_balance" />
                </TableHead>
                <TableHead
                  className="cursor-pointer select-none hover:text-foreground"
                  onClick={() => toggleSort("last_transaction_at")}
                >
                  Last Transaction <SortIcon col="last_transaction_at" />
                </TableHead>
                <TableHead className="text-right pr-4">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableSkeleton />
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="py-12 text-center text-sm text-muted-foreground">
                    No tenants match your filters.
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((row) => (
                  <TableRow
                    key={row.tenant_id}
                    className="cursor-pointer group"
                    onClick={() => openLedger(row)}
                  >
                    <TableCell className="pl-4">
                      <span className="font-medium text-sm group-hover:underline">
                        {row.tenant_name}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <span
                        className={`tabular-nums font-semibold text-sm ${
                          row.credit_balance < 100
                            ? "text-amber-400"
                            : row.credit_balance < 500
                              ? "text-foreground"
                              : "text-emerald-400"
                        }`}
                      >
                        {row.credit_balance.toLocaleString()}
                      </span>
                      {row.credit_balance < 100 && (
                        <span className="ml-1.5 text-[10px] text-amber-400/70">low</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(row.last_transaction_at)}
                    </TableCell>
                    <TableCell className="text-right pr-4" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => openGrant(row)}
                      >
                        <Coins className="h-3 w-3 mr-1" />
                        Grant
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Grant modal */}
      <GrantCreditsModal
        open={grantOpen}
        target={grantTarget}
        onClose={() => { setGrantOpen(false); setGrantTarget(null) }}
        onSuccess={() => {
          showFeedback("success", `Credits granted to ${grantTarget?.tenant_name ?? "tenant"}.`)
          load()
        }}
      />

      {/* Ledger modal */}
      <LedgerModal
        open={ledgerOpen}
        tenantId={ledgerTenantId}
        tenantName={ledgerTenantName}
        onClose={() => { setLedgerOpen(false); setLedgerTenantId(null) }}
      />
    </div>
  )
}
