"use client"

interface ConsentToggleProps {
  consentType: string
  label: string
  description: string
  granted: boolean
  grantedAt?: string | null
  withdrawnAt?: string | null
  onChange: (granted: boolean) => void
}

export function ConsentToggle({
  consentType,
  label,
  description,
  granted,
  grantedAt,
  withdrawnAt,
  onChange,
}: ConsentToggleProps) {
  return (
    <article className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-medium text-foreground">{label}</h4>
          <p className="text-xs text-muted-foreground">{description}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">Lawful basis: consent</p>
          <p className="text-[11px] text-muted-foreground">
            {granted ? `Granted on ${grantedAt ?? "-"}` : `Withdrawn on ${withdrawnAt ?? "-"}`}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={granted}
          aria-label={consentType}
          onClick={() => onChange(!granted)}
          className={`relative h-6 w-11 rounded-full transition ${granted ? "bg-[hsl(var(--brand-success))]" : "bg-muted"}`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${granted ? "left-5" : "left-0.5"}`}
          />
        </button>
      </div>
    </article>
  )
}

