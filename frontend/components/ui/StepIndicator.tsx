import { ORG_SETUP_STEP_NAMES } from "@/components/org-setup/constants"

interface OnboardingStepIndicatorProps {
  currentStep: number
  totalSteps?: number
  step?: never
}

interface OrgSetupStepIndicatorProps {
  step: number
  currentStep?: never
  totalSteps?: never
}

/**
 * Shared step indicator for onboarding and org setup flows.
 */
export type StepIndicatorProps =
  | OnboardingStepIndicatorProps
  | OrgSetupStepIndicatorProps

export function StepIndicator(props: StepIndicatorProps) {
  if (typeof props.step === "number") {
    const totalSteps = ORG_SETUP_STEP_NAMES.length
    const current = Math.min(Math.max(props.step, 1), totalSteps)
    const progress = (current / totalSteps) * 100

    return (
      <div className="space-y-3 rounded-xl border border-border bg-card/70 p-4">
        <p className="text-sm text-muted-foreground">
          Step {current} of {totalSteps} -{" "}
          <span className="text-foreground">
            {ORG_SETUP_STEP_NAMES[current - 1]}
          </span>
        </p>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-[hsl(var(--brand-primary))] transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    )
  }

  const { currentStep, totalSteps = 5 } = props

  return (
    <div className="flex items-center gap-2" aria-label="Onboarding steps">
      {Array.from({ length: totalSteps }).map((_, index) => {
        const step = index + 1
        const active = step === currentStep
        const completed = step < currentStep

        return (
          <div
            key={step}
            className={[
              "h-2 flex-1 rounded-full transition-colors",
              active
                ? "bg-[hsl(var(--brand-primary))]"
                : completed
                  ? "bg-[hsl(var(--brand-success))]"
                  : "bg-muted",
            ].join(" ")}
            title={`Step ${step}`}
          />
        )
      })}
    </div>
  )
}
