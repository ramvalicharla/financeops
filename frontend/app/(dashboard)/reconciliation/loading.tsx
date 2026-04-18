import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/ui/TableSkeleton"
import { Table, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export default function LoadingBoundary() {
  return (
    <div className="space-y-6 p-6 animate-in fade-in duration-500">
      <section className="flex flex-col md:flex-row md:items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-80" />
        </div>
        <Skeleton className="h-9 w-32" />
      </section>
      <div className="grid gap-4 md:grid-cols-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-3 w-48" />
          </div>
        ))}
      </div>
      <div className="rounded-md border border-border shadow-sm overflow-hidden bg-card">
        <Table>
          <TableHeader className="bg-muted/50 border-b border-border">
            <TableRow>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
              <TableHead><Skeleton className="h-4 w-28" /></TableHead>
              <TableHead><Skeleton className="h-4 w-16" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableSkeleton rows={6} cols={4} />
        </Table>
      </div>
    </div>
  )
}
