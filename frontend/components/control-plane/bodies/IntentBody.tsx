"use client"

import { useMemo, useState, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import { getIntent, type ControlPlaneIntent } from "@/lib/api/control-plane"
import { controlPlaneQueryKeys } from "@/lib/query/controlPlane"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { GuardFailureCard, IntentStepper, StateBadge } from "@/components/ui"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface IntentBodyProps {
  intentId?: string | null
  showRefreshButton?: boolean
}

type IntentTab = "intent" | "execution" | "audit"

const INTENT_TABS: Array<{ id: IntentTab; label: string; description: string }> = [
  { id: "intent", label: "Intent", description: "Lifecycle and validation" },
  { id: "execution", label: "Execution", description: "Job linkage and timing" },
  { id: "audit", label: "Audit", description: "Evidence and approval trail" },
]

const INTENT_STEPS = [
  { key: "draft", label: "Draft" },
  { key: "validated", label: "Validated" },
  { key: "submitted", label: "Submitted" },
  { key: "approved", label: "Approved" },
  { key: "executed", label: "Executed" },
]

const STEP_MATCHERS: Array<{ step: string; matches: string[] }> = [
  { step: "executed", matches: ["EXECUTED", "POSTED", "RECORDED", "COMPLETED", "SUCCEEDED"] },
  { step: "approved", matches: ["APPROVED"] },
  { step: "submitted", matches: ["SUBMITTED", "REVIEWED"] },
  { step: "validated", matches: ["VALIDATED", "CHECKED"] },
]

const summarizeValue = (value: unknown): string => {
  if (value === null) {
    return "null"
  }
  if (Array.isArray(value)) {
    return `array(${value.length})`
  }
  switch (typeof value) {
    case "string":
      return value
    case "number":
    case "boolean":
      return String(value)
    case "object":
      return "object"
    default:
      return "unknown"
  }
}

const getIntentStepIndex = (status: string): number => {
  const normalized = status.toUpperCase()
  if (["REJECTED", "FAILED", "ERROR"].includes(normalized)) {
    return 0
  }

  const matched = STEP_MATCHERS.find((entry) => entry.matches.some((match) => normalized.includes(match)))
  if (!matched) {
    return 0
  }

  return INTENT_STEPS.findIndex((step) => step.key === matched.step)
}

function TabButton({
  active,
  children,
  description,
  onClick,
}: {
  active: boolean
  children: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-2xl border px-3 py-2 text-left text-xs transition-colors",
        active
          ? "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.1)] text-foreground"
          : "border-border bg-card text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      <p className="font-medium">{children}</p>
      <p className="mt-1 text-[11px] text-muted-foreground">{description}</p>
    </button>
  )
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string
  value: string
  detail?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 break-words font-medium text-foreground">{value}</p>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  )
}

function SectionCard({
  title,
  eyebrow,
  children,
}: {
  title: string
  eyebrow: string
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-border bg-background p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{eyebrow}</p>
      <h3 className="mt-1 text-sm font-semibold text-foreground">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function StructuredValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">-</span>
  }

  if (Array.isArray(value)) {
    if (!value.length) {
      return <span className="text-muted-foreground">Empty list</span>
    }

    return (
      <div className="flex flex-wrap gap-2">
        {value.slice(0, 6).map((entry, index) => (
          <span key={index} className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground">
            {summarizeValue(entry)}
          </span>
        ))}
        {value.length > 6 ? (
          <span className="text-xs text-muted-foreground">+{value.length - 6} more</span>
        ) : null}
      </div>
    )
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
    if (!entries.length) {
      return <span className="text-muted-foreground">Empty object</span>
    }

    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {entries.slice(0, 6).map(([key, nested]) => (
          <div key={key} className="rounded-xl border border-border bg-card px-3 py-2">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
            <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(nested)}</p>
          </div>
        ))}
        {entries.length > 6 ? (
          <div className="rounded-xl border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
            +{entries.length - 6} more fields
          </div>
        ) : null}
      </div>
    )
  }

  return <span className="break-words text-sm text-foreground">{String(value)}</span>
}

function LabelValueList({
  rows,
}: {
  rows: Array<{ label: string; value: ReactNode }>
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="rounded-xl border border-border bg-card px-3 py-3">
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{row.label}</p>
          <div className="mt-1 text-sm text-foreground">{row.value}</div>
        </div>
      ))}
    </div>
  )
}

export function IntentBody({ intentId, showRefreshButton = true }: IntentBodyProps) {
  const selectedIntentId = useControlPlaneStore((state) => state.selected_intent_id)
  const openEvidenceDrawer = useControlPlaneStore((state) => state.openEvidenceDrawer)
  const [activeTab, setActiveTab] = useState<IntentTab>("intent")
  const resolvedIntentId = intentId ?? selectedIntentId

  const intentQuery = useQuery({
    queryKey: controlPlaneQueryKeys.intent(resolvedIntentId),
    queryFn: async () => (resolvedIntentId ? getIntent(resolvedIntentId) : null),
    enabled: Boolean(resolvedIntentId),
  })

  const intent = intentQuery.data
  const guardResults = intent?.guard_results
  const events: NonNullable<ControlPlaneIntent["events"]> =
    intent && "events" in intent && Array.isArray(intent.events) ? intent.events : []

  const validationRows = useMemo(() => {
    if (!guardResults) {
      return []
    }
    return Object.entries(guardResults).filter(([key]) => key !== "overall_passed")
  }, [guardResults])

  const currentStepIndex = getIntentStepIndex(intent?.status ?? "")
  const validationStatus = guardResults?.overall_passed ? "Pass" : "Needs attention"
  const recordRefEntries = intent?.record_refs ? Object.entries(intent.record_refs) : []
  const intentPayload = intent?.payload
  const payloadEntries = intentPayload ? Object.entries(intentPayload) : []
  const operationValue =
    intentPayload && typeof intentPayload === "object" && !Array.isArray(intentPayload)
      ? (intentPayload as Record<string, unknown>).operation
      : null
  const approvalEvents = events.filter((event) =>
    ["APPROVED", "REVIEWED", "SUBMITTED", "VALIDATED", "EXECUTED", "REJECTED"].includes(
      (event.to_status ?? event.event_type ?? "").toUpperCase(),
    ),
  )

  if (intentQuery.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-20 animate-pulse rounded-2xl bg-muted/60" />
        ))}
      </div>
    )
  }

  if (!resolvedIntentId) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        No data yet. Select a backend-confirmed intent to inspect it here.
      </div>
    )
  }

  if (intentQuery.error) {
    return (
      <div className="rounded-2xl border border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.12)] p-4 text-sm">
        <p className="font-medium text-foreground">Intent details failed to load</p>
        <p className="mt-1 text-muted-foreground">
          {intentQuery.error instanceof Error
            ? intentQuery.error.message
            : "The backend did not return the selected intent."}
        </p>
        <p className="mt-2 text-muted-foreground">Refresh the page or reopen the intent from its originating action.</p>
      </div>
    )
  }

  if (!intent) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-muted/30 p-4 text-sm text-muted-foreground">
        No backend intent data was returned for the selected identifier.
      </div>
    )
  }

  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Intent ID" value={intent.intent_id} detail={intent.intent_type} />
        <MetricCard label="Status" value={intent.status} detail={intent.module_key} />
        <MetricCard label="Job ID" value={intent.job_id ?? "-"} detail={intent.source_channel} />
        <MetricCard label="Next Action" value={intent.next_action ?? "-"} detail={intent.target_type} />
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {INTENT_TABS.map((tab) => (
          <TabButton
            key={tab.id}
            active={activeTab === tab.id}
            description={tab.description}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </TabButton>
        ))}
      </div>

      {activeTab === "intent" ? (
        <div className="space-y-4">
          <section className="rounded-2xl border border-border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Lifecycle</p>
                <div className="mt-2">
                  <StateBadge status={intent.status} label={`${intent.status} status`} />
                </div>
              </div>
              <div className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                Step {Math.max(currentStepIndex + 1, 1)} of {INTENT_STEPS.length}
              </div>
            </div>
            <IntentStepper
              className="mt-4"
              currentStep={currentStepIndex + 1}
              steps={INTENT_STEPS.map((step) => ({
                id: step.key,
                title: step.label,
                description: `Backend-governed ${step.label.toLowerCase()} state`,
              }))}
            />
          </section>

          <SectionCard title="Core Details" eyebrow="Intent">
            <LabelValueList
              rows={[
                { label: "Requested by", value: intent.requested_by_user_id },
                { label: "Requested role", value: intent.requested_by_role },
                { label: "Requested at", value: intent.requested_at ?? "-" },
                { label: "Submitted at", value: intent.submitted_at ?? "-" },
                { label: "Validated at", value: intent.validated_at ?? "-" },
                { label: "Approved at", value: intent.approved_at ?? "-" },
                ...(operationValue ? [{ label: "Operation", value: String(operationValue) }] : []),
              ]}
            />
          </SectionCard>

          <SectionCard title="Validation Summary" eyebrow="Governance">
            <div className="flex flex-wrap items-center gap-2">
              <StateBadge
                status={guardResults?.overall_passed ? "success" : "failed"}
                label={validationStatus}
              />
              <span className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                {validationRows.length} guard checks
              </span>
            </div>

            {!guardResults?.overall_passed && validationRows.length ? (
              <div className="mt-4">
                <GuardFailureCard
                  title="Guard checks need attention"
                  message="The backend returned validation results that require review before execution can proceed."
                  violations={validationRows.map(([key, value]) => ({
                    label: key,
                    detail: summarizeValue(value),
                  }))}
                  recommendation="Inspect the structured checks below and resolve the failing guard conditions before retrying the governed action."
                  tone="warning"
                />
              </div>
            ) : null}

            {validationRows.length ? (
              <div className="mt-4 space-y-3">
                {validationRows.map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border bg-card px-3 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-foreground">{key}</p>
                        <p className="mt-1 text-xs text-muted-foreground">Structured backend guard result</p>
                      </div>
                      <span className="rounded-full border border-border bg-background px-2.5 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                        {summarizeValue(value)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                No step-level validation details were returned for this intent.
              </p>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "execution" ? (
        <div className="space-y-4">
          <SectionCard title="Execution Summary" eyebrow="Execution">
            <LabelValueList
              rows={[
                { label: "Executor job", value: intent.job_id ?? "-" },
                { label: "Executed at", value: intent.executed_at ?? "-" },
                { label: "Recorded at", value: intent.recorded_at ?? "-" },
                { label: "Current action", value: intent.next_action ?? "-" },
              ]}
            />
          </SectionCard>

          <SectionCard title="Job Linkage" eyebrow="Execution">
            {intent.job_id ? (
              <div className="rounded-xl border border-border bg-card px-3 py-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Linked job</p>
                <p className="mt-1 break-all font-mono text-sm text-foreground">{intent.job_id}</p>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No backend job was attached to this intent yet.</p>
            )}
          </SectionCard>

          <SectionCard title="Execution Events" eyebrow="Execution">
            {events.length ? (
              <div className="space-y-3">
                {events.map((event) => (
                  <div key={event.event_id} className="rounded-xl border border-border bg-card px-3 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-sm font-medium text-foreground">{event.event_type}</p>
                      <p className="text-xs text-muted-foreground">{event.event_at ?? "unknown time"}</p>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {event.actor_role ?? "system"} - {event.actor_user_id ?? "unknown"}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {event.from_status ?? "-"} {"->"} {event.to_status ?? "-"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No execution events were returned for this intent yet.</p>
            )}
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "audit" ? (
        <div className="space-y-4">
          <SectionCard title="Approval Chain" eyebrow="Audit">
            {approvalEvents.length ? (
              <div className="space-y-3">
                {approvalEvents.map((event) => (
                  <div key={event.event_id} className="rounded-xl border border-border bg-card px-3 py-3">
                    <p className="text-sm font-medium text-foreground">{event.event_type}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {event.actor_role ?? "system"} - {event.actor_user_id ?? "unknown"} - {event.event_at ?? "unknown time"}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No approval-chain events were returned for this intent yet.
              </p>
            )}
          </SectionCard>

          <SectionCard title="Record References" eyebrow="Audit">
            {recordRefEntries.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {recordRefEntries.map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border bg-card px-3 py-3">
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
                    <p className="mt-1 break-words text-sm text-foreground">{summarizeValue(value)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No record references were returned for this intent.</p>
            )}
          </SectionCard>

          <SectionCard title="Intent Payload Summary" eyebrow="Audit">
            {payloadEntries.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {payloadEntries.map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border bg-card px-3 py-3">
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{key}</p>
                    <StructuredValue value={value} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No intent payload was returned for this intent.</p>
            )}
          </SectionCard>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {showRefreshButton ? (
          <Button type="button" variant="outline" onClick={() => void intentQuery.refetch()}>
            Refresh Intent
          </Button>
        ) : null}
        <Button type="button" variant="outline" onClick={() => openEvidenceDrawer("intent", intent.intent_id)}>
          Open Evidence
        </Button>
      </div>
    </div>
  )
}
