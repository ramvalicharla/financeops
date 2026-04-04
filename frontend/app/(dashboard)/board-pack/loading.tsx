function TableSkeleton({ title }: { title: string }) {
  return (
    <div className="space-y-6 animate-pulse">
      <div>
        <div className="h-8 w-44 rounded bg-muted/40" />
        <div className="mt-2 h-4 w-64 rounded bg-muted/30" />
      </div>
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 grid grid-cols-3 gap-3 border-b border-border pb-4">
          <div className="h-4 rounded bg-muted/40" />
          <div className="h-4 rounded bg-muted/40" />
          <div className="h-4 rounded bg-muted/40" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={`${title}-row-${index}`} className="grid grid-cols-3 gap-3">
              <div className="h-12 rounded-md bg-muted/30" />
              <div className="h-12 rounded-md bg-muted/30" />
              <div className="h-12 rounded-md bg-muted/30" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function BoardPackLoading() {
  return <TableSkeleton title="board-pack" />
}
