"use client"

import { useEffect, useState, useMemo } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Search, FileText, Receipt, Users, Building, Activity, FileSpreadsheet, Layers, PieChart } from "lucide-react"

import { searchGlobal } from "@/lib/api/search"
import type { SearchModuleType } from "@/lib/types/search"
import { PaginationBar } from "@/components/ui/PaginationBar"
import { useUIStore } from "@/lib/store/ui"
import { cn } from "@/lib/utils"

const MODULE_TABS: { label: string, value: string }[] = [
  { label: "All Results", value: "all" },
  { label: "Journals", value: "journal" },
  { label: "Expenses", value: "expense" },
  { label: "Reports", value: "report" },
  { label: "Users", value: "user" },
  { label: "Entities", value: "entity" },
]

const getIconForModule = (module: SearchModuleType) => {
  switch (module) {
    case "journal": return <FileSpreadsheet className="h-4 w-4" />
    case "expense": return <Receipt className="h-4 w-4" />
    case "report": return <PieChart className="h-4 w-4" />
    case "user": return <Users className="h-4 w-4" />
    case "entity": return <Building className="h-4 w-4" />
    default: return <FileText className="h-4 w-4" />
  }
}

export default function PageClient() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const urlQuery = searchParams?.get("q") ?? ""
  
  const [localQuery, setLocalQuery] = useState(urlQuery)
  const [activeModule, setActiveModule] = useState<string>("all")
  
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  const addRecentSearch = useUIStore((state) => state.addRecentSearch)

  // Sync back local query if URL changes externally
  useEffect(() => {
    setLocalQuery(urlQuery)
  }, [urlQuery])

  // Reset pagination when query or tab changes
  useEffect(() => {
    setPage(1)
  }, [urlQuery, activeModule])

  const { data, isLoading, error } = useQuery({
    queryKey: ["global-search-page", urlQuery, activeModule, page, pageSize],
    queryFn: () => searchGlobal({ 
      q: urlQuery, 
      module: activeModule, 
      limit: pageSize, 
      offset: (page - 1) * pageSize 
    }),
    enabled: urlQuery.length >= 2,
    staleTime: 60000,
  })

  // Ensure query executes immediately on enter, updating the URL string.
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (localQuery.trim().length >= 2) {
      addRecentSearch(localQuery.trim())
      router.push(`/search?q=${encodeURIComponent(localQuery.trim())}`)
    }
  }

  const totalResults = data?.meta.total_results ?? 0
  const searchTime = data?.meta.query_time_ms ?? 0

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6 lg:p-8">
      {/* ── Search Input Header ───────────────────────────────────────── */}
      <form onSubmit={handleSearchSubmit} className="relative mt-2">
        <div className="relative flex items-center shadow-lg rounded-2xl">
          <Search className="absolute left-4 h-6 w-6 text-muted-foreground" />
          <input
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Search thousands of journals, reports, expenses..."
            className="h-14 w-full rounded-2xl border border-border bg-card pl-14 pr-32 text-lg text-foreground placeholder:text-muted-foreground outline-none focus:border-[hsl(var(--brand-primary)/0.5)] focus:ring-4 focus:ring-[hsl(var(--brand-primary)/0.1)] transition-all"
            autoFocus
          />
          <button
            type="submit"
            className="absolute right-2 rounded-xl bg-[hsl(var(--brand-primary))] px-6 py-2 text-sm font-semibold text-primary-foreground hover:bg-[hsl(var(--brand-primary)/0.9)] transition-colors"
          >
            Search
          </button>
        </div>
      </form>

      {/* ── Tabs & Stats ──────────────────────────────────────────────── */}
      {urlQuery.length >= 2 ? (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-2">
          <div className="flex items-center gap-1 overflow-x-auto no-scrollbar mask-gradient-right">
            {MODULE_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setActiveModule(tab.value)}
                className={cn(
                  "whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent focus-visible:outline-none",
                  activeModule === tab.value 
                    ? "bg-[hsl(var(--brand-primary)/0.15)] text-[hsl(var(--brand-primary))] hover:bg-[hsl(var(--brand-primary)/0.2)]" 
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="shrink-0 text-xs text-muted-foreground">
            {isLoading ? "Searching..." : `${totalResults} results (${searchTime}ms)`}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-center opacity-60">
           <Layers className="h-16 w-16 text-muted-foreground mb-4" />
           <p className="text-lg font-medium">Global Semantic Search</p>
           <p className="text-sm text-muted-foreground mt-1 max-w-sm">Enter at least 2 characters to search across Journals, Expenses, Users, Reports, and Entities seamlessly.</p>
        </div>
      )}

      {/* ── Results Container ─────────────────────────────────────────── */}
      {urlQuery.length >= 2 && (
        <div className="space-y-4">
          {error ? (
             <div className="rounded-xl border border-destructive/50 bg-destructive/10 p-6 text-center text-sm text-destructive">
               Failed to fetch search results. Backend may be unreachable.
             </div>
          ) : isLoading ? (
            <div className="space-y-3">
               {Array.from({ length: 5 }).map((_, i) => (
                 <div key={i} className="h-24 w-full animate-pulse rounded-xl border border-border bg-card/60" />
               ))}
            </div>
          ) : data?.data && data.data.length > 0 ? (
            <>
              <div className="flex flex-col gap-3">
                {data.data.map(row => (
                  <Link 
                    key={row.id} 
                    href={row.href}
                    className="group flex flex-col gap-3 sm:flex-row sm:items-start rounded-xl border border-border bg-card p-4 hover:border-[hsl(var(--brand-primary)/0.5)] hover:shadow-md transition-all active:scale-[0.995]"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground group-hover:bg-[hsl(var(--brand-primary))] group-hover:text-primary-foreground transition-colors">
                      {getIconForModule(row.module)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-semibold text-foreground truncate">{row.title}</h3>
                        {row.status && (
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                            {row.status}
                          </span>
                        )}
                        <span className="ml-auto flex shrink-0 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          {row.module}
                        </span>
                      </div>
                      {row.subtitle && (
                        <p className="mt-1 text-sm text-muted-foreground">{row.subtitle}</p>
                      )}
                      <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground/70">
                         {row.amount !== null && (
                           <span className="font-mono font-medium text-foreground">
                             {new Intl.NumberFormat("en-US", { style: "currency", currency: row.currency || "USD" }).format(row.amount)}
                           </span>
                         )}
                         <span title="Created At">
                           {new Date(row.created_at).toLocaleDateString()}
                         </span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>

              {totalResults > 0 && (
                <div className="pt-4 pb-12">
                  <PaginationBar
                    total={totalResults}
                    skip={(page - 1) * pageSize}
                    limit={pageSize}
                    onPageChange={(newSkip) => setPage(Math.floor(newSkip / pageSize) + 1)}
                  />
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center opacity-80">
              <Activity className="h-12 w-12 text-muted-foreground mb-3" />
              <p className="text-base font-medium">No results found for &quot;{urlQuery}&quot;</p>
              <p className="text-sm text-muted-foreground mt-1">Try adjusting your filters or search terms.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
