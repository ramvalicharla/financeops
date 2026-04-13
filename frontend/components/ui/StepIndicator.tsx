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

    return (
      <div className="rounded-xl border border-border bg-card/70 p-4">
        <ol className="flex items-center gap-1 overflow-x-auto" aria-label="Setup progress">
          {ORG_SETUP_STEP_NAMES.map((name, index) => {
            const stepNum = index + 1
            const isCompleted = stepNum < current
            const isActive = stepNum === current

            return (
              <li key={name} className="flex min-w-0 items-center">
                {index > 0 ? (
                  <div
                    className={[
                      "mx-1 h-px w-4 shrink-0",
                      isCompleted ? "bg-[hsl(var(--brand-success))]" : "bg-border",
                    ].join(" ")}
                    aria-hidden="true"
                  />
                ) : null}
                <div
                  className={[
                    "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors",
                    isActive
                      ? "bg-[hsl(var(--brand-primary)/0.15)] text-[hsl(var(--brand-primary))] ring-1 ring-[hsl(var(--brand-primary)/0.4)]"
                      : isCompleted
                        ? "bg-[hsl(var(--brand-success)/0.12)] text-[hsl(var(--brand-success))]"
                        : "text-muted-foreground",
                  ].join(" ")}
                >
                  {isCompleted ? (
                    <svg
                      aria-hidden="true"
                      className="h-3 w-3 shrink-0"
                      viewBox="0 0 12 12"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="2,6 5,9 10,3" />
                    </svg>
                  ) : (
                    <span
                      className={[
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px]",
                        isActive
                          ? "bg-[hsl(var(--brand-primary))] text-white"
                          : "bg-muted text-muted-foreground",
                      ].join(" ")}
                    >
                      {stepNum}
                    </span>
                  )}
                  <span className="hidden sm:inline">{name}</span>
                </div>
              </li>
            )
          })}
        </ol>
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
