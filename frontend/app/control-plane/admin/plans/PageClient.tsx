"use client"

import { useEffect, useState } from "react"
import {
  Plus,
  Pencil,
  PowerOff,
  CheckCircle2,
  AlertTriangle,
  CreditCard,
  Users,
  Building2,
  Clock,
  Zap,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog } from "@/components/ui/Dialog"
import { ConfirmDialog } from "@/components/ui/ConfirmDialog"
import {
  adminListPlans,
  adminCreatePlan,
  adminUpdatePlan,
  adminDeactivatePlan,
} from "@/lib/api/admin"
import type { AdminBillingPlan, AdminPlanFormValues } from "@/lib/types/admin"

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const KNOWN_MODULES = [
  "gl_tb_reconciliation",
  "bank_reconciliation",
  "gst_reconciliation",
  "working_capital",
  "month_end_checklist",
  "auditor_access",
  "mis_manager",
  "fixed_assets",
  "prepaid_expenses",
  "invoices",
  "payments",
  "treasury",
  "budget_forecast",
  "ai_cfo",
  "board_pack",
  "consolidation",
] as const

const MODULE_LABELS: Record<string, string> = {
  gl_tb_reconciliation: "GL/TB Reconciliation",
  bank_reconciliation: "Bank Reconciliation",
  gst_reconciliation: "GST Reconciliation",
  working_capital: "Working Capital",
  month_end_checklist: "Month-End Checklist",
  auditor_access: "Auditor Access",
  mis_manager: "MIS Manager",
  fixed_assets: "Fixed Assets",
  prepaid_expenses: "Prepaid Expenses",
  invoices: "Invoices",
  payments: "Payments",
  treasury: "Treasury",
  budget_forecast: "Budget & Forecast",
  ai_cfo: "AI CFO",
  board_pack: "Board Pack",
  consolidation: "Consolidation",
}

const EMPTY_FORM: AdminPlanFormValues = {
  name: "",
  plan_tier: "starter",
  pricing_type: "flat",
  price: "0",
  billing_cycle: "monthly",
  currency: "USD",
  included_credits: 0,
  max_entities: 1,
  max_connectors: 1,
  max_users: 5,
  trial_days: 14,
  is_active: true,
  modules_enabled: {},
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

type FormErrors = Partial<Record<keyof AdminPlanFormValues, string>>

function validate(v: AdminPlanFormValues): FormErrors {
  const errors: FormErrors = {}
  if (!v.name.trim()) errors.name = "Name is required"
  const price = parseFloat(v.price)
  if (isNaN(price) || price < 0) errors.price = "Must be ≥ 0"
  if (v.max_users < 1) errors.max_users = "Must be ≥ 1"
  if (v.max_entities < 1) errors.max_entities = "Must be ≥ 1"
  if (v.max_connectors < 0) errors.max_connectors = "Must be ≥ 0"
  if (v.trial_days < 0) errors.trial_days = "Must be ≥ 0"
  if (v.included_credits < 0) errors.included_credits = "Must be ≥ 0"
  return errors
}

// ---------------------------------------------------------------------------
// Plan card
// ---------------------------------------------------------------------------

const TIER_COLORS: Record<string, string> = {
  starter: "border-blue-500/30 bg-blue-500/5",
  professional: "border-purple-500/30 bg-purple-500/5",
  enterprise: "border-amber-500/30 bg-amber-500/5",
}

function PlanCard({
  plan,
  onEdit,
  onDeactivate,
}: {
  plan: AdminBillingPlan
  onEdit: (p: AdminBillingPlan) => void
  onDeactivate: (p: AdminBillingPlan) => void
}) {
  const tierColor = TIER_COLORS[plan.plan_tier?.toLowerCase()] ?? "border-border"
  const moduleCount = Object.values(plan.modules_enabled ?? {}).filter(Boolean).length

  return (
    <Card className={`border ${tierColor} ${plan.is_active ? "" : "opacity-60"}`}>
      <CardHeader className="pb-3 flex flex-row items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-base font-semibold truncate">{plan.name}</CardTitle>
            <span className="rounded-full px-2 py-0.5 text-[11px] font-medium bg-muted text-muted-foreground capitalize">
              {plan.plan_tier}
            </span>
            {!plan.is_active && (
              <span className="rounded-full px-2 py-0.5 text-[11px] font-medium bg-destructive/20 text-destructive">
                Inactive
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1 capitalize">
            {plan.pricing_type} · {plan.billing_cycle}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onEdit(plan)}
            title="Edit plan"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          {plan.is_active && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onDeactivate(plan)}
              title="Deactivate plan"
              className="text-destructive hover:text-destructive"
            >
              <PowerOff className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Price */}
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold tabular-nums">
            {plan.currency === "INR" ? "₹" : "$"}{plan.price ?? "0"}
          </span>
          <span className="text-sm text-muted-foreground">/{plan.billing_cycle === "annual" ? "yr" : "mo"}</span>
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CreditCard className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
            <span>{(plan.included_credits ?? 0).toLocaleString()} credits</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Users className="h-3.5 w-3.5 text-blue-400 shrink-0" />
            <span>{plan.max_users} users</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Building2 className="h-3.5 w-3.5 text-purple-400 shrink-0" />
            <span>{plan.max_entities} entities</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5 text-amber-400 shrink-0" />
            <span>{plan.trial_days}d trial</span>
          </div>
        </div>

        {/* Modules */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Zap className="h-3.5 w-3.5 text-violet-400 shrink-0" />
          <span>{moduleCount} module{moduleCount !== 1 ? "s" : ""} enabled</span>
        </div>

        {moduleCount > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {Object.entries(plan.modules_enabled ?? {})
              .filter(([, v]) => v)
              .slice(0, 4)
              .map(([k]) => (
                <span key={k} className="rounded px-1.5 py-0.5 text-[10px] bg-muted text-muted-foreground">
                  {MODULE_LABELS[k] ?? k}
                </span>
              ))}
            {moduleCount > 4 && (
              <span className="rounded px-1.5 py-0.5 text-[10px] bg-muted text-muted-foreground">
                +{moduleCount - 4} more
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function PlanCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-3 w-20 mt-1" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-8 w-24" />
        <div className="grid grid-cols-2 gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-3 w-full" />)}
        </div>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Plan form modal
// ---------------------------------------------------------------------------

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null
  return <p className="mt-1 text-xs text-destructive">{msg}</p>
}

function Label({ htmlFor, children }: { htmlFor: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="block text-xs font-medium text-muted-foreground mb-1">
      {children}
    </label>
  )
}

function SelectField({
  id,
  value,
  onChange,
  options,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

function PlanFormModal({
  open,
  onClose,
  initialValues,
  onSuccess,
}: {
  open: boolean
  onClose: () => void
  initialValues: AdminPlanFormValues & { id?: string }
  onSuccess: () => void
}) {
  const isEdit = Boolean(initialValues.id)
  const [values, setValues] = useState<AdminPlanFormValues & { id?: string }>(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setValues(initialValues)
      setErrors({})
      setApiError(null)
    }
  }, [open, initialValues])

  const set = <K extends keyof AdminPlanFormValues>(key: K, val: AdminPlanFormValues[K]) =>
    setValues((prev) => ({ ...prev, [key]: val }))

  const toggleModule = (mod: string) =>
    setValues((prev) => ({
      ...prev,
      modules_enabled: {
        ...prev.modules_enabled,
        [mod]: !prev.modules_enabled[mod],
      },
    }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs = validate(values)
    if (Object.keys(errs).length) {
      setErrors(errs)
      return
    }
    setSubmitting(true)
    setApiError(null)
    try {
      if (isEdit && values.id) {
        await adminUpdatePlan(values.id, values)
      } else {
        await adminCreatePlan(values)
      }
      onSuccess()
      onClose()
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "Failed to save plan")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEdit ? "Edit Plan" : "Create Plan"}
      description={isEdit ? "Updates create a new immutable revision." : "Fill in all required fields."}
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        {apiError && (
          <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            {apiError}
          </div>
        )}

        {/* Row 1: Name + Tier */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="plan-name">Name *</Label>
            <Input
              id="plan-name"
              value={values.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Starter Monthly"
              className="h-9"
            />
            <FieldError msg={errors.name} />
          </div>
          <div>
            <Label htmlFor="plan-tier">Tier *</Label>
            <SelectField
              id="plan-tier"
              value={values.plan_tier}
              onChange={(v) => set("plan_tier", v as AdminPlanFormValues["plan_tier"])}
              options={[
                { value: "starter", label: "Starter" },
                { value: "professional", label: "Professional" },
                { value: "enterprise", label: "Enterprise" },
              ]}
            />
          </div>
        </div>

        {/* Row 2: Price + Currency + Cycle */}
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <Label htmlFor="plan-price">Price *</Label>
            <Input
              id="plan-price"
              type="number"
              min="0"
              step="0.01"
              value={values.price}
              onChange={(e) => set("price", e.target.value)}
              className="h-9"
            />
            <FieldError msg={errors.price} />
          </div>
          <div>
            <Label htmlFor="plan-currency">Currency</Label>
            <SelectField
              id="plan-currency"
              value={values.currency}
              onChange={(v) => set("currency", v)}
              options={[
                { value: "USD", label: "USD ($)" },
                { value: "INR", label: "INR (₹)" },
              ]}
            />
          </div>
          <div>
            <Label htmlFor="plan-cycle">Billing Cycle</Label>
            <SelectField
              id="plan-cycle"
              value={values.billing_cycle}
              onChange={(v) => set("billing_cycle", v as AdminPlanFormValues["billing_cycle"])}
              options={[
                { value: "monthly", label: "Monthly" },
                { value: "annual", label: "Annual" },
              ]}
            />
          </div>
        </div>

        {/* Row 3: Pricing type */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="plan-pricing-type">Pricing Type</Label>
            <SelectField
              id="plan-pricing-type"
              value={values.pricing_type}
              onChange={(v) => set("pricing_type", v as AdminPlanFormValues["pricing_type"])}
              options={[
                { value: "flat", label: "Flat" },
                { value: "tiered", label: "Tiered" },
                { value: "usage", label: "Usage" },
                { value: "hybrid", label: "Hybrid" },
              ]}
            />
          </div>
          <div>
            <Label htmlFor="plan-credits">Included Credits</Label>
            <Input
              id="plan-credits"
              type="number"
              min="0"
              value={values.included_credits}
              onChange={(e) => set("included_credits", parseInt(e.target.value) || 0)}
              className="h-9"
            />
            <FieldError msg={errors.included_credits} />
          </div>
        </div>

        {/* Row 4: Limits */}
        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <Label htmlFor="plan-max-users">Max Users</Label>
            <Input
              id="plan-max-users"
              type="number"
              min="1"
              value={values.max_users}
              onChange={(e) => set("max_users", parseInt(e.target.value) || 1)}
              className="h-9"
            />
            <FieldError msg={errors.max_users} />
          </div>
          <div>
            <Label htmlFor="plan-max-entities">Max Entities</Label>
            <Input
              id="plan-max-entities"
              type="number"
              min="1"
              value={values.max_entities}
              onChange={(e) => set("max_entities", parseInt(e.target.value) || 1)}
              className="h-9"
            />
            <FieldError msg={errors.max_entities} />
          </div>
          <div>
            <Label htmlFor="plan-max-connectors">Max Connectors</Label>
            <Input
              id="plan-max-connectors"
              type="number"
              min="0"
              value={values.max_connectors}
              onChange={(e) => set("max_connectors", parseInt(e.target.value) || 0)}
              className="h-9"
            />
            <FieldError msg={errors.max_connectors} />
          </div>
          <div>
            <Label htmlFor="plan-trial-days">Trial Days</Label>
            <Input
              id="plan-trial-days"
              type="number"
              min="0"
              value={values.trial_days}
              onChange={(e) => set("trial_days", parseInt(e.target.value) || 0)}
              className="h-9"
            />
            <FieldError msg={errors.trial_days} />
          </div>
        </div>

        {/* Modules */}
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-2">Modules Enabled</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-lg border border-border p-3">
            {KNOWN_MODULES.map((mod) => (
              <label
                key={mod}
                className="flex items-center gap-2 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={!!values.modules_enabled[mod]}
                  onChange={() => toggleModule(mod)}
                  className="h-3.5 w-3.5 rounded border-input accent-primary"
                />
                <span className="text-xs text-muted-foreground">{MODULE_LABELS[mod]}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Active toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={values.is_active}
            onChange={(e) => set("is_active", e.target.checked)}
            className="h-3.5 w-3.5 rounded border-input accent-primary"
          />
          <span className="text-sm">Active</span>
        </label>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
          <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting}>
            {submitting ? (
              <span className="flex items-center gap-1.5">
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Saving…
              </span>
            ) : (
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {isEdit ? "Save Changes" : "Create Plan"}
              </span>
            )}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AdminPlansPageClient() {
  const [plans, setPlans] = useState<AdminBillingPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<(AdminPlanFormValues & { id?: string }) | null>(null)

  const [deactivating, setDeactivating] = useState<AdminBillingPlan | null>(null)
  const [deactivateLoading, setDeactivateLoading] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    adminListPlans()
      .then(setPlans)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Failed to load plans"))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const showFeedback = (type: "success" | "error", msg: string) => {
    setFeedback({ type, msg })
    setTimeout(() => setFeedback(null), 4000)
  }

  const openCreate = () => {
    setEditingPlan({ ...EMPTY_FORM })
    setModalOpen(true)
  }

  const openEdit = (plan: AdminBillingPlan) => {
    setEditingPlan({
      id: plan.id,
      name: plan.name,
      plan_tier: plan.plan_tier as AdminPlanFormValues["plan_tier"],
      pricing_type: (plan.pricing_type || "flat") as AdminPlanFormValues["pricing_type"],
      price: plan.price ?? "0",
      billing_cycle: (plan.billing_cycle || "monthly") as AdminPlanFormValues["billing_cycle"],
      currency: plan.currency || "USD",
      included_credits: plan.included_credits ?? 0,
      max_entities: plan.max_entities ?? 1,
      max_connectors: plan.max_connectors ?? 1,
      max_users: plan.max_users ?? 5,
      trial_days: plan.trial_days ?? 0,
      is_active: plan.is_active,
      modules_enabled: plan.modules_enabled ?? {},
    })
    setModalOpen(true)
  }

  const handleDeactivateConfirm = async () => {
    if (!deactivating) return
    setDeactivateLoading(true)
    try {
      await adminDeactivatePlan(deactivating.id)
      showFeedback("success", `"${deactivating.name}" has been deactivated.`)
      load()
    } catch (err: unknown) {
      showFeedback("error", err instanceof Error ? err.message : "Failed to deactivate plan")
    } finally {
      setDeactivateLoading(false)
      setDeactivating(null)
    }
  }

  const activePlans = plans.filter((p) => p.is_active)
  const inactivePlans = plans.filter((p) => !p.is_active)

  return (
    <div className="space-y-8 p-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Plan Management</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {loading ? "Loading…" : `${activePlans.length} active plan${activePlans.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Plan
        </Button>
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

      {/* Active plans */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
          Active Plans
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {loading
            ? [...Array(4)].map((_, i) => <PlanCardSkeleton key={i} />)
            : activePlans.length === 0
              ? (
                <div className="col-span-full py-12 text-center text-sm text-muted-foreground border border-dashed border-border rounded-lg">
                  No active plans. Create one to get started.
                </div>
              )
              : activePlans.map((p) => (
                <PlanCard key={p.id} plan={p} onEdit={openEdit} onDeactivate={setDeactivating} />
              ))}
        </div>
      </section>

      {/* Inactive plans (collapsed section) */}
      {!loading && inactivePlans.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">
            Inactive Plans ({inactivePlans.length})
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {inactivePlans.map((p) => (
              <PlanCard key={p.id} plan={p} onEdit={openEdit} onDeactivate={setDeactivating} />
            ))}
          </div>
        </section>
      )}

      {/* Create / Edit modal */}
      {editingPlan && (
        <PlanFormModal
          open={modalOpen}
          onClose={() => { setModalOpen(false); setEditingPlan(null) }}
          initialValues={editingPlan}
          onSuccess={() => {
            showFeedback("success", editingPlan.id ? "Plan updated." : "Plan created.")
            load()
          }}
        />
      )}

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={Boolean(deactivating)}
        title="Deactivate Plan"
        description={`Deactivating "${deactivating?.name}" will create an inactive revision. Existing subscribers are not affected immediately.`}
        confirmLabel="Deactivate"
        variant="destructive"
        isLoading={deactivateLoading}
        onConfirm={handleDeactivateConfirm}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  )
}
