import Link from "next/link"

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-12">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 text-center">
        <h1 className="text-2xl font-semibold text-foreground">Page Not Found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you requested does not exist.
        </p>
        <Link
          href="/mis"
          className="mt-6 inline-flex rounded-md border border-border px-4 py-2 text-sm text-foreground transition-colors hover:bg-muted"
        >
          Go To Dashboard
        </Link>
      </div>
    </main>
  )
}
