export default function AuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md space-y-8">
        <div className="space-y-2 text-center animate-pulse">
          <div className="mx-auto h-3 w-24 rounded bg-muted/40" />
          <div className="mx-auto h-8 w-36 rounded bg-muted/40" />
        </div>
        <div className="animate-pulse rounded-lg border border-border bg-card p-6 shadow-sm">
          <div className="mb-6 space-y-3">
            <div className="h-6 w-40 rounded bg-muted/40" />
            <div className="h-4 w-56 rounded bg-muted/30" />
          </div>
          <div className="space-y-4">
            <div className="h-10 rounded-md bg-muted/30" />
            <div className="h-10 rounded-md bg-muted/30" />
            <div className="h-10 rounded-md bg-muted/40" />
          </div>
        </div>
      </div>
    </div>
  )
}
