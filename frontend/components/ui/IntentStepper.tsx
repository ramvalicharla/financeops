import type { ReactNode } from "react"

import { Check, Circle, CircleAlert } from "lucide-react"

import { cn } from "@/lib/utils"

export type IntentStepStatus = "pending" | "current" | "complete" | "blocked" | "failed"

export interface IntentStep {
  id?: string
  title: string
  description?: string
  status?: IntentStepStatus
}

export interface IntentStepperProps {
  steps: IntentStep[]
  currentStep?: number
  className?: string
}

const resolveStatus = (
  step: IntentStep,
  index: number,
  currentStep?: number,
): IntentStepStatus => {
  if (step.status) {
    return step.status
  }

  if (typeof currentStep !== "number") {
    return index === 0 ? "current" : "pending"
  }

  if (index + 1 < currentStep) {
    return "complete"
  }

  if (index + 1 === currentStep) {
    return "current"
  }

  return "pending"
}

const statusStyles: Record<IntentStepStatus, string> = {
  pending: "border-border bg-card text-muted-foreground",
  current: "border-[hsl(var(--brand-primary)/0.45)] bg-[hsl(var(--brand-primary)/0.08)] text-foreground",
  complete: "border-[hsl(var(--brand-success)/0.45)] bg-[hsl(var(--brand-success)/0.08)] text-foreground",
  blocked: "border-[hsl(var(--brand-warning)/0.45)] bg-[hsl(var(--brand-warning)/0.1)] text-foreground",
  failed: "border-[hsl(var(--brand-danger)/0.45)] bg-[hsl(var(--brand-danger)/0.08)] text-foreground",
}

const statusIcons: Record<IntentStepStatus, ReactNode> = {
  pending: <Circle className="h-4 w-4" aria-hidden="true" />,
  current: <CircleAlert className="h-4 w-4" aria-hidden="true" />,
  complete: <Check className="h-4 w-4" aria-hidden="true" />,
  blocked: <CircleAlert className="h-4 w-4" aria-hidden="true" />,
  failed: <CircleAlert className="h-4 w-4" aria-hidden="true" />,
}

/**
 * Shared governance stepper for intent and execution lifecycles.
 */
export function IntentStepper({
  steps,
  currentStep,
  className,
}: IntentStepperProps) {
  return (
    <ol className={cn("grid gap-3 sm:grid-cols-2 xl:grid-cols-4", className)}>
      {steps.map((step, index) => {
        const status = resolveStatus(step, index, currentStep)
        const isLast = index === steps.length - 1

        return (
          <li key={step.id ?? `${step.title}-${index}`} className="flex">
            <div className="flex w-full items-stretch gap-3">
              <div
                className={cn(
                  "flex min-h-[4.5rem] flex-1 items-start gap-3 rounded-2xl border p-3",
                  statusStyles[status],
                )}
              >
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-background/80 text-foreground">
                  {statusIcons[status]}
                </div>
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-semibold text-foreground">{step.title}</p>
                  {step.description ? (
                    <p className="text-sm leading-5 text-muted-foreground">
                      {step.description}
                    </p>
                  ) : null}
                </div>
              </div>
              {!isLast ? (
                <div className="hidden w-3 items-center justify-center xl:flex" aria-hidden="true">
                  <div className="h-px w-full bg-border" />
                </div>
              ) : null}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
