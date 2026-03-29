interface StepIndicatorProps {
  currentStep: number
  totalSteps?: number
}

export function StepIndicator({ currentStep, totalSteps = 5 }: StepIndicatorProps) {
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
