function ContentSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-10 w-56 rounded-md bg-muted/40" />
      <div className="grid gap-4 md:grid-cols-3">
        <div className="h-28 rounded-xl border border-border bg-card/60" />
        <div className="h-28 rounded-xl border border-border bg-card/60" />
        <div className="h-28 rounded-xl border border-border bg-card/60" />
      </div>
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 h-5 w-40 rounded bg-muted/40" />
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={`dashboard-row-${index}`} className="h-12 rounded-md bg-muted/30" />
          ))}
        </div>
      </div>
    </div>
  )
}

export default function DashboardLoading() {
  return (
    <div className="h-screen overflow-hidden bg-background text-foreground">
      <div className="hidden h-full w-60 animate-pulse border-r border-border bg-card md:fixed md:inset-y-0 md:left-0 md:flex md:flex-col">
        <div className="border-b border-border px-4 py-4">
          <div className="h-3 w-24 rounded bg-muted/40" />
        </div>
        <div className="flex-1 space-y-3 p-3">
          {Array.from({ length: 10 }).map((_, index) => (
            <div key={`sidebar-item-${index}`} className="h-9 rounded-md bg-muted/30" />
          ))}
        </div>
      </div>
      <div className="flex h-full flex-col md:pl-60">
        <div className="h-16 animate-pulse border-b border-border bg-background/95 px-4 py-4 md:px-6">
          <div className="h-7 w-48 rounded bg-muted/40" />
        </div>
        <main className="flex-1 overflow-y-auto p-6">
          <ContentSkeleton />
        </main>
      </div>
    </div>
  )
}
