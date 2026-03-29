"use client"

import { Building2, Factory, HeartPulse, Laptop, ShoppingBag, Users, Wand2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { OnboardingIndustry } from "@/lib/types/template-onboarding"

interface IndustryCard {
  id: OnboardingIndustry
  label: string
  description: string
  icon: typeof Building2
}

const industries: IndustryCard[] = [
  {
    id: "saas",
    label: "SaaS",
    description: "Subscription-led growth with retention and ARR focus.",
    icon: Laptop,
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    description: "COGS, inventory turns, and margin control.",
    icon: Factory,
  },
  {
    id: "retail",
    label: "Retail",
    description: "Category-level revenue and weekly trading cadence.",
    icon: ShoppingBag,
  },
  {
    id: "professional_services",
    label: "Professional Services",
    description: "Utilisation and revenue-per-head visibility.",
    icon: Users,
  },
  {
    id: "healthcare",
    label: "Healthcare",
    description: "Revenue-cycle and operational cost tracking.",
    icon: HeartPulse,
  },
  {
    id: "general",
    label: "General",
    description: "Balanced setup for broad finance operations.",
    icon: Building2,
  },
  {
    id: "it_services",
    label: "IT Services",
    description: "Project margin and managed-services performance.",
    icon: Wand2,
  },
]

interface Step1WelcomeProps {
  selectedIndustry: OnboardingIndustry | null
  onSelectIndustry: (industry: OnboardingIndustry) => void
  onContinue: () => void
  loading?: boolean
}

export function Step1Welcome({
  selectedIndustry,
  onSelectIndustry,
  onContinue,
  loading = false,
}: Step1WelcomeProps) {
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold text-foreground">Let&apos;s set up your workspace</h1>
        <p className="text-sm text-muted-foreground">
          Choose an industry template to pre-configure board packs, reports, and delivery schedules.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {industries.map((industry) => {
          const Icon = industry.icon
          const active = selectedIndustry === industry.id
          return (
            <button
              key={industry.id}
              type="button"
              onClick={() => onSelectIndustry(industry.id)}
              className={[
                "rounded-lg border p-4 text-left transition",
                active
                  ? "border-[hsl(var(--brand-primary))] bg-[hsl(var(--brand-primary)/0.15)]"
                  : "border-border bg-card hover:border-[hsl(var(--brand-primary)/0.5)]",
              ].join(" ")}
            >
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4" />
                <span className="font-medium text-foreground">{industry.label}</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{industry.description}</p>
            </button>
          )
        })}
      </div>

      <div className="flex justify-end">
        <Button type="button" onClick={onContinue} disabled={!selectedIndustry || loading}>
          Continue
        </Button>
      </div>
    </section>
  )
}
