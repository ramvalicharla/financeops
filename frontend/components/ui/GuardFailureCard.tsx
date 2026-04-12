import type { ComponentProps, ReactNode } from "react"

import { AlertTriangle, ShieldAlert } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export interface GuardFailureItem {
  label: string
  detail?: string
}

export interface GuardFailureCardProps {
  title: string
  message: string
  violations?: GuardFailureItem[]
  recommendation?: string
  tone?: "warning" | "danger"
  primaryAction?: ReactNode
  secondaryAction?: ReactNode
  className?: string
}

const toneClasses: Record<NonNullable<GuardFailureCardProps["tone"]>, string> = {
  warning: "border-[hsl(var(--brand-warning)/0.35)] bg-[hsl(var(--brand-warning)/0.08)]",
  danger: "border-[hsl(var(--brand-danger)/0.35)] bg-[hsl(var(--brand-danger)/0.08)]",
}

/**
 * Structured guard-failure surface for governed flows.
 * Keep the content evidence-based and backend-derived.
 */
export function GuardFailureCard({
  title,
  message,
  violations = [],
  recommendation,
  tone = "warning",
  primaryAction,
  secondaryAction,
  className,
}: GuardFailureCardProps) {
  const Icon = tone === "danger" ? ShieldAlert : AlertTriangle

  return (
    <section
      className={cn(
        "rounded-2xl border p-4 shadow-sm",
        toneClasses[tone],
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 rounded-full p-2",
            tone === "danger"
              ? "bg-[hsl(var(--brand-danger)/0.14)] text-[hsl(var(--brand-danger))]"
              : "bg-[hsl(var(--brand-warning)/0.14)] text-[hsl(var(--brand-warning))]",
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground">{message}</p>
          </div>

          {violations.length > 0 ? (
            <ul className="space-y-2">
              {violations.map((violation, index) => (
                <li
                  key={`${violation.label}-${index}`}
                  className="rounded-xl border border-border/60 bg-background/70 px-3 py-2"
                >
                  <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
                    {violation.label}
                  </p>
                  {violation.detail ? (
                    <p className="mt-1 text-sm text-foreground">{violation.detail}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}

          {recommendation ? (
            <p className="text-sm text-foreground">
              <span className="font-medium">Recommendation:</span> {recommendation}
            </p>
          ) : null}

          {primaryAction || secondaryAction ? (
            <div className="flex flex-wrap gap-2 pt-1">
              {secondaryAction}
              {primaryAction}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}

export function GuardFailureAction({
  children,
  variant = "outline",
  ...props
}: ComponentProps<typeof Button>) {
  return (
    <Button type="button" size="sm" variant={variant} {...props}>
      {children}
    </Button>
  )
}
