import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/ui/TableSkeleton"
import { Table, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export default function LoadingBoundary() {
  return (
    <div className="space-y-6 p-6 animate-in fade-in duration-500">
      <section className="flex flex-col md:flex-row md:items-start justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-28" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-9 w-24" />
      </section>
      <div className="rounded-md border border-border shadow-sm overflow-hidden bg-card">
        <Table>
          <TableHeader className="bg-muted/50 border-b border-border">
            <TableRow>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
              <TableHead><Skeleton className="h-4 w-32" /></TableHead>
              <TableHead><Skeleton className="h-4 w-20" /></TableHead>
              <TableHead><Skeleton className="h-4 w-24" /></TableHead>
            </TableRow>
          </TableHeader>
          <TableSkeleton rows={6} cols={4} />
        </Table>
      </div>
    </div>
  )
}
