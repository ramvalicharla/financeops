"use client"

import type { ReactNode } from "react"

interface PageScaffoldProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  children: ReactNode
}

export function PageScaffold({
  eyebrow = "Control Plane",
  title,
  description,
  actions,
  children,
}: PageScaffoldProps) {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border bg-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{eyebrow}</p>
            <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
            <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>
          </div>
          {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      </section>
      {children}
    </div>
  )
}
