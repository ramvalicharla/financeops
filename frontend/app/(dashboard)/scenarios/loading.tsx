import { Skeleton } from "@/components/ui/skeleton"

export default function LoadingBoundary() {
  return (
    <div className="space-y-6 p-6 animate-in fade-in duration-500">
      <section className="flex flex-col md:flex-row md:items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-44" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-24" />
        </div>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-36" />
            <Skeleton className="h-10 w-20" />
            <Skeleton className="h-3 w-52" />
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-border bg-card p-4 space-y-4">
        <Skeleton className="h-5 w-40" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-2 border-b border-border last:border-0">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-16 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  )
}
