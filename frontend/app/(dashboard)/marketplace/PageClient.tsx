"use client"

import Link from "next/link"
import { useCallback, useEffect, useMemo, useState } from "react"
import { listMarketplaceTemplates } from "@/lib/api/marketplace"
import type { MarketplaceTemplate } from "@/lib/types/marketplace"
import { TemplateCard } from "@/components/marketplace/TemplateCard"

type FilterKey = "all" | "mis_template" | "report_template" | "board_pack" | "industry_pack" | "free"

const FILTERS: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "All" },
  { key: "mis_template", label: "MIS Templates" },
  { key: "report_template", label: "Report Templates" },
  { key: "board_pack", label: "Board Packs" },
  { key: "industry_pack", label: "Industry Packs" },
  { key: "free", label: "Free" },
]

export default function MarketplacePage() {
  const [templates, setTemplates] = useState<MarketplaceTemplate[]>([])
  const [activeFilter, setActiveFilter] = useState<FilterKey>("all")
  const [sortBy, setSortBy] = useState("featured")
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listMarketplaceTemplates({
        template_type:
          activeFilter !== "all" && activeFilter !== "free"
            ? activeFilter
            : undefined,
        is_free: activeFilter === "free" ? true : undefined,
        sort_by: sortBy,
        limit: 60,
        offset: 0,
      })
      setTemplates(payload.data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load marketplace templates")
    } finally {
      setLoading(false)
    }
  }, [activeFilter, sortBy])

  useEffect(() => {
    void load()
  }, [activeFilter, sortBy, load])

  const visibleTemplates = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) {
      return templates
    }
    return templates.filter((row) => {
      const tags = (row.tags ?? []).join(" ").toLowerCase()
      return (
        row.title.toLowerCase().includes(needle) ||
        row.description.toLowerCase().includes(needle) ||
        tags.includes(needle)
      )
    })
  }, [search, templates])

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Marketplace</h1>
          <p className="text-sm text-muted-foreground">
            Discover templates from the Finqor contributor ecosystem.
          </p>
        </div>
        <Link
          href="/marketplace/contribute"
          className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Become a Contributor
        </Link>
      </header>

      <section className="space-y-3 rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          {FILTERS.map((filter) => (
            <button
              key={filter.key}
              type="button"
              onClick={() => setActiveFilter(filter.key)}
              className={`rounded-full border px-3 py-1 text-xs ${
                activeFilter === filter.key
                  ? "border-[hsl(var(--brand-primary))] text-foreground"
                  : "border-border text-muted-foreground"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
            placeholder="Search title or tags"
          />
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="featured">Featured</option>
            <option value="newest">Newest</option>
            <option value="popular">Most Popular</option>
            <option value="price_asc">Price</option>
            <option value="rating">Rating</option>
          </select>
        </div>
      </section>

      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading templates...</p> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibleTemplates.map((template) => (
          <TemplateCard key={template.id} template={template} />
        ))}
      </section>
      {!loading && visibleTemplates.length === 0 ? (
        <p className="text-sm text-muted-foreground">No templates found for this filter.</p>
      ) : null}

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-base font-semibold text-foreground">Become a Contributor</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Publish your MIS, reporting, and industry templates. Earn recurring credits from every purchase.
        </p>
        <Link
          href="/marketplace/contribute"
          className="mt-3 inline-flex rounded-md border border-border px-3 py-2 text-sm text-foreground"
        >
          Open Contributor Portal
        </Link>
      </section>
    </div>
  )
}
