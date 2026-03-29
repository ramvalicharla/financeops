import Link from "next/link"
import { RAGBadge } from "@/components/compliance/RAGBadge"

interface TrustSummaryCardProps {
  title: string
  subtitle: string
  rag: "green" | "amber" | "red" | "grey"
  stats: string
  href: string
}

export function TrustSummaryCard({ title, subtitle, rag, stats, href }: TrustSummaryCardProps) {
  return (
    <article className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <RAGBadge status={rag} />
      </div>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
      <p className="mt-3 text-sm text-foreground">{stats}</p>
      <Link href={href} className="mt-4 inline-flex text-sm text-[hsl(var(--brand-primary))]">
        View Details
      </Link>
    </article>
  )
}

