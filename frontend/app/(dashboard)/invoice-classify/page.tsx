"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  classifyInvoice,
  createClassificationRule,
  deleteClassificationRule,
  getReviewQueue,
  listClassificationRules,
  listClassifications,
  reviewClassification,
  routeClassification,
  type ClassificationMethod,
  type ClassificationRule,
  type InvoiceClassification,
  type InvoiceClassificationType,
} from "@/lib/api/invoiceClassifier"
import { useTenantStore } from "@/lib/store/tenant"
import { useFormattedAmount } from "@/hooks/useFormattedAmount"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { Input } from "@/components/ui/input"

const classificationOptions: InvoiceClassificationType[] = [
  "FIXED_ASSET",
  "PREPAID_EXPENSE",
  "DIRECT_EXPENSE",
  "CAPEX",
  "OPEX",
  "UNCERTAIN",
]

const confidencePct = (raw: string): number => {
  const value = Number(raw)
  if (!Number.isFinite(value)) {
    return 0
  }
  return value * 100
}

const confidenceClass = (pct: number): string => {
  if (pct >= 90) {
    return "bg-[hsl(var(--brand-success)/0.2)] text-[hsl(var(--brand-success))]"
  }
  if (pct >= 70) {
    return "bg-[hsl(var(--brand-warning)/0.2)] text-[hsl(var(--brand-warning))]"
  }
  return "bg-[hsl(var(--brand-danger)/0.2)] text-[hsl(var(--brand-danger))]"
}

const classBadge = (classification: InvoiceClassificationType): string => {
  if (classification === "FIXED_ASSET") {
    return "bg-blue-500/20 text-blue-300"
  }
  if (classification === "PREPAID_EXPENSE") {
    return "bg-amber-500/20 text-amber-300"
  }
  if (classification === "DIRECT_EXPENSE") {
    return "bg-emerald-500/20 text-emerald-300"
  }
  if (classification === "UNCERTAIN") {
    return "bg-rose-500/20 text-rose-300"
  }
  return "bg-muted text-muted-foreground"
}

type Tab = "classify" | "queue" | "history" | "rules"

export default function InvoiceClassifierPage() {
  const queryClient = useQueryClient()
  const { fmt } = useFormattedAmount()
  const activeEntityId = useTenantStore((state) => state.active_entity_id)
  const entityRoles = useTenantStore((state) => state.entity_roles)

  const [tab, setTab] = useState<Tab>("classify")
  const [skip, setSkip] = useState(0)
  const [limit, setLimit] = useState(20)
  const [historyClassification, setHistoryClassification] = useState<string>("ALL")
  const [historyMethod, setHistoryMethod] = useState<string>("ALL")

  const [invoiceNumber, setInvoiceNumber] = useState("")
  const [vendorName, setVendorName] = useState("")
  const [invoiceDate, setInvoiceDate] = useState("")
  const [invoiceAmount, setInvoiceAmount] = useState("")
  const [lineDescription, setLineDescription] = useState("")
  const [latestResult, setLatestResult] = useState<InvoiceClassification | null>(null)

  const [ruleName, setRuleName] = useState("")
  const [ruleDescription, setRuleDescription] = useState("")
  const [rulePatternType, setRulePatternType] = useState<ClassificationRule["pattern_type"]>("VENDOR_NAME")
  const [rulePatternValue, setRulePatternValue] = useState("")
  const [ruleAmountMin, setRuleAmountMin] = useState("")
  const [ruleAmountMax, setRuleAmountMax] = useState("")
  const [ruleClassification, setRuleClassification] = useState<InvoiceClassificationType>("DIRECT_EXPENSE")
  const [ruleConfidence, setRuleConfidence] = useState("0.9500")
  const [rulePriority, setRulePriority] = useState("100")
  const [fieldErrors, setFieldErrors] = useState<{
    activeEntityId?: string
    invoiceNumber?: string
    vendorName?: string
    invoiceDate?: string
    invoiceAmount?: string
    lineDescription?: string
    ruleName?: string
    rulePatternValue?: string
    ruleConfidence?: string
    rulePriority?: string
  }>({})

  const queueQuery = useQuery({
    queryKey: ["invoice-review-queue", activeEntityId, skip, limit],
    queryFn: () => getReviewQueue({ entity_id: activeEntityId ?? "", skip, limit }),
    enabled: Boolean(activeEntityId),
  })

  const historyQuery = useQuery({
    queryKey: ["invoice-history", activeEntityId, historyClassification, historyMethod, skip, limit],
    queryFn: () =>
      listClassifications({
        entity_id: activeEntityId ?? "",
        classification:
          historyClassification === "ALL"
            ? undefined
            : (historyClassification as InvoiceClassificationType),
        method: historyMethod === "ALL" ? undefined : (historyMethod as ClassificationMethod),
        skip,
        limit,
      }),
    enabled: Boolean(activeEntityId),
  })

  const rulesQuery = useQuery({
    queryKey: ["invoice-rules"],
    queryFn: listClassificationRules,
  })

  const classifyMutation = useMutation({
    mutationFn: () =>
      classifyInvoice({
        entity_id: activeEntityId ?? "",
        invoice_number: invoiceNumber,
        vendor_name: vendorName,
        invoice_date: invoiceDate || null,
        invoice_amount: invoiceAmount,
        line_description: lineDescription,
      }),
    onSuccess: (data) => {
      setLatestResult(data)
      void queryClient.invalidateQueries({ queryKey: ["invoice-review-queue", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["invoice-history", activeEntityId] })
    },
  })

  const reviewMutation = useMutation({
    mutationFn: ({ id, classification }: { id: string; classification: InvoiceClassificationType }) =>
      reviewClassification(id, { confirmed_classification: classification }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-review-queue", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["invoice-history", activeEntityId] })
    },
  })

  const routeMutation = useMutation({
    mutationFn: (id: string) => routeClassification(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-review-queue", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["invoice-history", activeEntityId] })
    },
  })

  const bulkApproveMutation = useMutation({
    mutationFn: async (rows: InvoiceClassification[]) => {
      for (const row of rows) {
        await reviewClassification(row.id, { confirmed_classification: row.classification })
      }
      return rows.length
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-review-queue", activeEntityId] })
      void queryClient.invalidateQueries({ queryKey: ["invoice-history", activeEntityId] })
    },
  })

  const createRuleMutation = useMutation({
    mutationFn: () =>
      createClassificationRule({
        rule_name: ruleName,
        description: ruleDescription || null,
        pattern_type: rulePatternType,
        pattern_value: rulePatternValue,
        amount_min: ruleAmountMin || null,
        amount_max: ruleAmountMax || null,
        classification: ruleClassification,
        confidence: ruleConfidence,
        priority: Number(rulePriority),
        is_active: true,
      }),
    onSuccess: () => {
      setRuleName("")
      setRuleDescription("")
      setRulePatternType("VENDOR_NAME")
      setRulePatternValue("")
      setRuleAmountMin("")
      setRuleAmountMax("")
      setRuleClassification("DIRECT_EXPENSE")
      setRuleConfidence("0.9500")
      setRulePriority("100")
      void queryClient.invalidateQueries({ queryKey: ["invoice-rules"] })
    },
  })

  const deleteRuleMutation = useMutation({
    mutationFn: (id: string) => deleteClassificationRule(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invoice-rules"] })
    },
  })

  const queueRows = queueQuery.data?.items ?? []
  const summary = useMemo(() => {
    const source = historyQuery.data?.items ?? []
    const total = source.length
    const mapped = source.filter((row) => row.routing_action !== null).length
    const confirmed = source.filter((row) => row.human_reviewed_at !== null || !row.requires_human_review).length
    const unmapped = source.filter((row) => row.routing_action === null).length
    const avg =
      total === 0
        ? 0
        : source.reduce((acc, row) => acc + confidencePct(row.confidence), 0) / total
    return { total, mapped, confirmed, unmapped, avg }
  }, [historyQuery.data])

  const handleClassify = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!activeEntityId) nextFieldErrors.activeEntityId = "Entity is required."
    if (!invoiceNumber.trim()) nextFieldErrors.invoiceNumber = "Invoice number is required."
    if (!vendorName.trim()) nextFieldErrors.vendorName = "Vendor is required."
    if (!invoiceAmount.trim()) nextFieldErrors.invoiceAmount = "Amount is required."
    if (!lineDescription.trim()) nextFieldErrors.lineDescription = "Line description is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    classifyMutation.mutate()
  }

  const handleCreateRule = () => {
    const nextFieldErrors: typeof fieldErrors = {}
    if (!ruleName.trim()) nextFieldErrors.ruleName = "Rule name is required."
    if (!rulePatternValue.trim()) nextFieldErrors.rulePatternValue = "Pattern value is required."
    if (!ruleConfidence.trim()) nextFieldErrors.ruleConfidence = "Confidence is required."
    if (!rulePriority.trim()) nextFieldErrors.rulePriority = "Priority is required."
    if (Object.keys(nextFieldErrors).length > 0) {
      setFieldErrors(nextFieldErrors)
      return
    }
    setFieldErrors({})
    createRuleMutation.mutate()
  }

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">AI Invoice Classifier</h1>
        <p className="text-sm text-muted-foreground">
          Classify invoices into fixed assets, prepaid expenses, or direct expenses with rule + AI support.
        </p>
      </header>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="grid gap-3 md:grid-cols-5">
          <FormField id="invoice-entity" label="Entity" error={fieldErrors.activeEntityId} required>
            <select
              value={activeEntityId ?? ""}
              onChange={(event) => useTenantStore.getState().setActiveEntity(event.target.value || null)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="">Select entity</option>
              {entityRoles.map((role) => (
                <option key={role.entity_id} value={role.entity_id}>
                  {role.entity_name}
                </option>
              ))}
            </select>
          </FormField>
          <div className="col-span-4 flex flex-wrap gap-2">
            <Button variant={tab === "classify" ? "default" : "outline"} onClick={() => setTab("classify")}>Classify</Button>
            <Button variant={tab === "queue" ? "default" : "outline"} onClick={() => setTab("queue")}>Review queue</Button>
            <Button variant={tab === "history" ? "default" : "outline"} onClick={() => setTab("history")}>All classifications</Button>
            <Button variant={tab === "rules" ? "default" : "outline"} onClick={() => setTab("rules")}>Rules</Button>
          </div>
        </div>
      </section>

      {tab === "classify" ? (
        <section className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <FormField id="invoice-number" label="Invoice number" error={fieldErrors.invoiceNumber} required>
              <Input value={invoiceNumber} onChange={(event) => setInvoiceNumber(event.target.value)} />
            </FormField>
            <FormField id="invoice-vendor" label="Vendor" error={fieldErrors.vendorName} required>
              <Input value={vendorName} onChange={(event) => setVendorName(event.target.value)} />
            </FormField>
            <FormField id="invoice-date" label="Invoice date">
              <Input type="date" value={invoiceDate} onChange={(event) => setInvoiceDate(event.target.value)} />
            </FormField>
            <FormField id="invoice-amount" label="Amount" error={fieldErrors.invoiceAmount} required>
              <Input value={invoiceAmount} onChange={(event) => setInvoiceAmount(event.target.value)} inputMode="decimal" />
            </FormField>
            <div className="md:col-span-2">
              <FormField id="invoice-notes" label="Line description" error={fieldErrors.lineDescription} required>
                <Input
                  value={lineDescription}
                  onChange={(event) => setLineDescription(event.target.value)}
                />
              </FormField>
            </div>
          </div>
          <Button
            onClick={handleClassify}
            disabled={!activeEntityId || !invoiceNumber || !vendorName || !invoiceAmount || !lineDescription || classifyMutation.isPending}
          >
            Classify Invoice
          </Button>

          {latestResult ? (
            <div className="rounded-lg border border-border p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-1 text-xs ${classBadge(latestResult.classification)}`}>
                  {latestResult.classification}
                </span>
                <span className={`rounded-full px-2 py-1 text-xs ${confidenceClass(confidencePct(latestResult.confidence))}`}>
                  {confidencePct(latestResult.confidence).toFixed(2)}%
                </span>
                <span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {latestResult.classification_method}
                </span>
              </div>
              {latestResult.requires_human_review ? (
                <p className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
                  Human review required before final routing.
                </p>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => routeMutation.mutate(latestResult.id)}
                  disabled={routeMutation.isPending}
                >
                  Route to module
                </Button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "queue" ? (
        <section className="space-y-3 rounded-xl border border-border bg-card p-4">
          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() => bulkApproveMutation.mutate(queueRows)}
              disabled={!queueRows.length || bulkApproveMutation.isPending}
            >
              Bulk approve
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Invoice</th>
                  <th className="px-4 py-2">Vendor</th>
                  <th className="px-4 py-2">Amount</th>
                  <th className="px-4 py-2">Suggested</th>
                  <th className="px-4 py-2">Confidence</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {queueRows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-2">{row.invoice_number}</td>
                    <td className="px-4 py-2">{row.vendor_name}</td>
                    <td className="px-4 py-2">{fmt(row.invoice_amount)}</td>
                    <td className="px-4 py-2">{row.classification}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs ${confidenceClass(confidencePct(row.confidence))}`}>
                        {confidencePct(row.confidence).toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-2">
                        <select
                          className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground"
                          defaultValue={row.classification}
                          onChange={(event) =>
                            reviewMutation.mutate({
                              id: row.id,
                              classification: event.target.value as InvoiceClassificationType,
                            })
                          }
                        >
                          {classificationOptions.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => routeMutation.mutate(row.id)}
                          disabled={routeMutation.isPending}
                        >
                          Route
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === "history" ? (
        <section className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-lg text-foreground">{summary.total}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-xs text-muted-foreground">Mapped</p>
              <p className="text-lg text-foreground">{summary.mapped}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-xs text-muted-foreground">Confirmed</p>
              <p className="text-lg text-foreground">{summary.confirmed}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-xs text-muted-foreground">Unmapped</p>
              <p className="text-lg text-foreground">{summary.unmapped}</p>
            </div>
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-xs text-muted-foreground">Avg confidence</p>
              <p className="text-lg text-foreground">{summary.avg.toFixed(2)}%</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <select
              value={historyClassification}
              onChange={(event) => setHistoryClassification(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="ALL">All classifications</option>
              {classificationOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <select
              value={historyMethod}
              onChange={(event) => setHistoryMethod(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="ALL">All methods</option>
              <option value="RULE_ENGINE">Rule engine</option>
              <option value="AI_GATEWAY">AI gateway</option>
              <option value="HUMAN_OVERRIDE">Human override</option>
            </select>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Invoice</th>
                  <th className="px-4 py-2">Vendor</th>
                  <th className="px-4 py-2">Amount</th>
                  <th className="px-4 py-2">Classification</th>
                  <th className="px-4 py-2">Method</th>
                  <th className="px-4 py-2">Confidence</th>
                  <th className="px-4 py-2">Routing</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(historyQuery.data?.items ?? []).map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-2">{row.invoice_number}</td>
                    <td className="px-4 py-2">{row.vendor_name}</td>
                    <td className="px-4 py-2">{fmt(row.invoice_amount)}</td>
                    <td className="px-4 py-2">{row.human_override ?? row.classification}</td>
                    <td className="px-4 py-2">{row.classification_method}</td>
                    <td className="px-4 py-2">{confidencePct(row.confidence).toFixed(2)}%</td>
                    <td className="px-4 py-2">{row.routing_action ?? "PENDING"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(Math.max(0, skip - limit))}
              disabled={skip === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSkip(skip + limit)}
              disabled={!(historyQuery.data?.has_more ?? false)}
            >
              Next
            </Button>
          </div>
        </section>
      ) : null}

      {tab === "rules" ? (
        <section className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <FormField id="invoice-rule-name" label="Rule name" error={fieldErrors.ruleName} required>
              <Input value={ruleName} onChange={(event) => setRuleName(event.target.value)} />
            </FormField>
            <select
              value={rulePatternType}
              onChange={(event) => setRulePatternType(event.target.value as ClassificationRule["pattern_type"])}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="VENDOR_NAME">Vendor name</option>
              <option value="DESCRIPTION_KEYWORD">Description keyword</option>
              <option value="AMOUNT_RANGE">Amount range</option>
              <option value="VENDOR_AND_KEYWORD">Vendor and keyword</option>
            </select>
            <select
              value={ruleClassification}
              onChange={(event) => setRuleClassification(event.target.value as InvoiceClassificationType)}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            >
              {classificationOptions.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
            <div className="md:col-span-3">
              <Input
                value={ruleDescription}
                onChange={(event) => setRuleDescription(event.target.value)}
                placeholder="Description"
              />
            </div>
            <div className="md:col-span-3">
              <FormField id="invoice-rule-pattern" label="Pattern value" error={fieldErrors.rulePatternValue} required>
                <Input
                  value={rulePatternValue}
                  onChange={(event) => setRulePatternValue(event.target.value)}
                />
              </FormField>
            </div>
            <FormField id="invoice-rule-amount-min" label="Amount min"><Input value={ruleAmountMin} onChange={(event) => setRuleAmountMin(event.target.value)} inputMode="decimal" /></FormField>
            <FormField id="invoice-rule-amount-max" label="Amount max"><Input value={ruleAmountMax} onChange={(event) => setRuleAmountMax(event.target.value)} inputMode="decimal" /></FormField>
            <FormField id="invoice-rule-confidence" label="Confidence" error={fieldErrors.ruleConfidence} required><Input
              value={ruleConfidence}
              onChange={(event) => setRuleConfidence(event.target.value)}
              inputMode="decimal"
            /></FormField>
            <FormField id="invoice-rule-priority" label="Priority" error={fieldErrors.rulePriority} required><Input value={rulePriority} onChange={(event) => setRulePriority(event.target.value)} inputMode="decimal" /></FormField>
          </div>
          <Button
            onClick={handleCreateRule}
            disabled={!ruleName || !rulePatternValue || !ruleConfidence || !rulePriority || createRuleMutation.isPending}
          >
            Add Rule
          </Button>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/30">
                <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2">Rule</th>
                  <th className="px-4 py-2">Pattern</th>
                  <th className="px-4 py-2">Classification</th>
                  <th className="px-4 py-2">Confidence</th>
                  <th className="px-4 py-2">Priority</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(rulesQuery.data ?? []).map((rule) => (
                  <tr key={rule.id}>
                    <td className="px-4 py-2">{rule.rule_name}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">
                      {rule.pattern_type}: {rule.pattern_value}
                    </td>
                    <td className="px-4 py-2">{rule.classification}</td>
                    <td className="px-4 py-2">{confidencePct(rule.confidence).toFixed(2)}%</td>
                    <td className="px-4 py-2">{rule.priority}</td>
                    <td className="px-4 py-2">{rule.is_active ? "Active" : "Inactive"}</td>
                    <td className="px-4 py-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => deleteRuleMutation.mutate(rule.id)}
                        disabled={deleteRuleMutation.isPending}
                      >
                        Deactivate
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
