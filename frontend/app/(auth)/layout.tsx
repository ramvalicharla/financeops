import type { ReactNode } from "react"

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main id="main-content" className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md space-y-8">
        <div className="space-y-2 text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Finqor
          </p>
          <h1 className="text-2xl font-semibold text-foreground">Finqor</h1>
        </div>
        {children}
      </div>
    </main>
  )
}
