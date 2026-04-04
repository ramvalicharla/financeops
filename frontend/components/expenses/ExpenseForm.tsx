"use client"

import { useEffect, useMemo, useState } from "react"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { FormField } from "@/components/ui/FormField"
import { submitExpense } from "@/lib/api/expenses"
import type { ExpenseClaim, ExpensePolicy } from "@/lib/types/expense"

const submitSchema = z.object({
  claim_date: z.string().min(1),
  vendor_name: z.string().min(2),
  category: z.enum([
    "meals",
    "travel",
    "accommodation",
    "office_supplies",
    "professional_fees",
    "other",
  ]),
  amount: z.string().regex(/^\d+(\.\d{1,2})?$/),
  currency: z.string().length(3),
  description: z.string().min(3),
  has_receipt: z.boolean(),
  justification: z.string().optional(),
})

interface ExpenseFormProps {
  policy: ExpensePolicy
  onSubmitted: (claim: ExpenseClaim) => void
}

interface PolicyFeedback {
  level: "ok" | "soft" | "hard"
  message: string
  violationType: string | null
}

const computePolicyFeedback = (
  policy: ExpensePolicy,
  payload: {
    category: string
    amount: string
    claimDate: string
    vendorName: string
    hasReceipt: boolean
  },
): PolicyFeedback => {
  const amount = Number.parseFloat(payload.amount || "0")
  const lowerVendor = payload.vendorName.toLowerCase()

  const personalHit = policy.personal_merchant_keywords.some((keyword) =>
    lowerVendor.includes(keyword.toLowerCase()),
  )
  if (personalHit) {
    return { level: "hard", message: "Personal merchant detected.", violationType: "personal_merchant" }
  }

  const receiptThreshold = Number.parseFloat(policy.receipt_required_above)
  if (!payload.hasReceipt && amount > receiptThreshold) {
    return { level: "soft", message: "Receipt required above policy threshold.", violationType: "receipt_missing" }
  }

  const categoryLimit =
    payload.category === "meals"
      ? Number.parseFloat(policy.meal_limit_per_day)
      : payload.category === "travel" || payload.category === "accommodation"
      ? Number.parseFloat(policy.travel_limit_per_night)
      : null

  if (categoryLimit !== null) {
    if (amount > categoryLimit * 1.5) {
      return { level: "hard", message: "Amount exceeds hard policy limit.", violationType: "hard_limit" }
    }
    if (amount > categoryLimit) {
      return { level: "soft", message: "Amount exceeds policy limit.", violationType: "soft_limit" }
    }
  }

  if (
    policy.round_number_flag_enabled &&
    amount > 500 &&
    Math.floor(amount) % 500 === 0
  ) {
    return { level: "soft", message: "Round-number expense flagged.", violationType: "round_number" }
  }

  const weekday = payload.claimDate ? new Date(payload.claimDate).getDay() : -1
  if (policy.weekend_flag_enabled && (weekday === 0 || weekday === 6)) {
    return { level: "soft", message: "Weekend expense flagged.", violationType: "weekend" }
  }

  return { level: "ok", message: "Within policy.", violationType: null }
}

export function ExpenseForm({ policy, onSubmitted }: ExpenseFormProps) {
  const [claimDate, setClaimDate] = useState(new Date().toISOString().slice(0, 10))
  const [vendorName, setVendorName] = useState("")
  const [category, setCategory] = useState("other")
  const [amount, setAmount] = useState("")
  const [currency, setCurrency] = useState("INR")
  const [description, setDescription] = useState("")
  const [hasReceipt, setHasReceipt] = useState(false)
  const [receiptUrl, setReceiptUrl] = useState<string | null>(null)
  const [justification, setJustification] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [feedback, setFeedback] = useState<PolicyFeedback>({
    level: "ok",
    message: "Within policy.",
    violationType: null,
  })
  const [fieldErrors, setFieldErrors] = useState<{
    claim_date?: string
    vendor_name?: string
    category?: string
    amount?: string
    currency?: string
    description?: string
    receipt?: string
    justification?: string
  }>({})

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setFeedback(
        computePolicyFeedback(policy, {
          category,
          amount,
          claimDate,
          vendorName,
          hasReceipt,
        }),
      )
    }, 300)
    return () => window.clearTimeout(handle)
  }, [policy, category, amount, claimDate, vendorName, hasReceipt])

  const requiresJustification = feedback.level === "soft"
  const submitDisabled = feedback.level === "hard" || submitting

  const feedbackClass = useMemo(() => {
    if (feedback.level === "hard") {
      return "border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.15)] text-[hsl(var(--brand-danger))]"
    }
    if (feedback.level === "soft") {
      return "border-amber-500/40 bg-amber-500/15 text-amber-300"
    }
    return "border-[hsl(var(--brand-success)/0.4)] bg-[hsl(var(--brand-success)/0.15)] text-[hsl(var(--brand-success))]"
  }, [feedback.level])

  const onReceiptSelected = (file: File | null) => {
    if (!file) {
      setReceiptUrl(null)
      setUploadProgress(0)
      return
    }
    setUploadProgress(25)
    window.setTimeout(() => setUploadProgress(65), 120)
    window.setTimeout(() => {
      setUploadProgress(100)
      setReceiptUrl(`https://uploads.local/${encodeURIComponent(file.name)}`)
      setHasReceipt(true)
    }, 260)
  }

  const submit = async () => {
    setError(null)
    const parsed = submitSchema.safeParse({
      claim_date: claimDate,
      vendor_name: vendorName,
      category,
      amount,
      currency,
      description,
      has_receipt: hasReceipt,
      justification: justification || undefined,
    })

    if (!parsed.success) {
      const nextFieldErrors: typeof fieldErrors = {}
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as keyof typeof fieldErrors
        if (!nextFieldErrors[key]) {
          nextFieldErrors[key] = issue.message
        }
      }
      setFieldErrors(nextFieldErrors)
      setError(null)
      return
    }

    if (requiresJustification && !justification.trim()) {
      setFieldErrors((current) => ({
        ...current,
        justification: "Justification is required for this policy warning.",
      }))
      setError(null)
      return
    }

    setFieldErrors({})
    setSubmitting(true)
    try {
      const claim = await submitExpense({
        vendor_name: vendorName,
        description,
        category,
        amount,
        currency,
        claim_date: claimDate,
        has_receipt: hasReceipt,
        receipt_url: receiptUrl,
        justification: justification || undefined,
      })
      onSubmitted(claim)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Submission failed")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className={`rounded-md border px-3 py-2 text-sm ${feedbackClass}`}>{feedback.message}</div>

      <div className="grid gap-3 md:grid-cols-2">
        <FormField id="expense-date" label="Expense date" error={fieldErrors.claim_date} required>
          <input
            type="date"
            value={claimDate}
            onChange={(event) => setClaimDate(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            required
          />
        </FormField>
        <FormField id="expense-vendor" label="Vendor" error={fieldErrors.vendor_name} required>
          <input
            value={vendorName}
            onChange={(event) => setVendorName(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            required
          />
        </FormField>
        <FormField id="expense-category" label="Category" error={fieldErrors.category} required>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            required
          >
            <option value="meals">Meals</option>
            <option value="travel">Travel</option>
            <option value="accommodation">Accommodation</option>
            <option value="office_supplies">Office Supplies</option>
            <option value="professional_fees">Professional Fees</option>
            <option value="other">Other</option>
          </select>
        </FormField>
        <FormField id="expense-amount" label="Amount" error={fieldErrors.amount} required>
          <input
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            inputMode="decimal"
            required
          />
        </FormField>
        <FormField id="expense-currency" label="Currency" error={fieldErrors.currency} required>
          <input
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            className="w-full rounded-md border border-border bg-background px-3 py-2"
            required
          />
        </FormField>
        <FormField id="expense-description" label="Description" error={fieldErrors.description} required>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="min-h-[100px] w-full rounded-md border border-border bg-background px-3 py-2 md:col-span-2"
            required
          />
        </FormField>
      </div>

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={hasReceipt} onChange={(event) => setHasReceipt(event.target.checked)} />
        Receipt available
      </label>

      <FormField id="expense-receipt" label="Receipt" hint="Upload a PDF or image of the receipt">
        <input
          type="file"
          onChange={(event) => onReceiptSelected(event.target.files?.[0] ?? null)}
          className="block w-full text-sm text-muted-foreground"
        />
      </FormField>
      {uploadProgress > 0 ? (
        <div className="h-2 w-full overflow-hidden rounded bg-muted">
          <div className="h-full bg-[hsl(var(--brand-primary))] transition-all" style={{ width: `${uploadProgress}%` }} />
        </div>
      ) : null}

      {requiresJustification ? (
        <FormField id="expense-notes" label="Notes" error={fieldErrors.justification}>
          <textarea
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
            className="min-h-[90px] w-full rounded-md border border-border bg-background px-3 py-2"
          />
        </FormField>
      ) : null}

      {error ? (
        <p className="rounded-md border border-[hsl(var(--brand-danger)/0.4)] bg-[hsl(var(--brand-danger)/0.15)] px-3 py-2 text-sm text-[hsl(var(--brand-danger))]">
          {error}
        </p>
      ) : null}

      <Button onClick={submit} disabled={submitDisabled}>
        Submit Expense
      </Button>
    </div>
  )
}
