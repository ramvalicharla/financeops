import type { ReactNode } from "react"
import Link from "next/link"

export default function OrgSetupLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(47,117,255,0.18),transparent_55%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.12),transparent_45%),hsl(var(--background))] text-foreground">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 py-8">
        <header className="mb-6">
          <Link href="/" className="text-sm uppercase tracking-[0.22em] text-muted-foreground">
            Finqor
          </Link>
        </header>
        <main id="main-content" className="mx-auto w-full max-w-4xl">{children}</main>
      </div>
    </div>
  )
}
