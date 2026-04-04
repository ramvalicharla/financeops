import type { ReactNode } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav aria-label="Marketing navigation" className="border-b border-border px-4 py-5 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <span className="text-xl font-semibold text-foreground">FinanceOps</span>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Link
              href="/login"
              className="text-sm text-muted-foreground transition hover:text-foreground"
            >
              Sign in
            </Link>
            <Button asChild>
              <Link href="/register">Start free trial</Link>
            </Button>
          </div>
        </div>
      </nav>
      <main id="main-content">{children}</main>
      <footer className="border-t border-border px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
          <span>(c) 2026 FinanceOps. All rights reserved.</span>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:gap-6 md:justify-end">
            <Link href="/legal/terms" className="transition hover:text-foreground">
              Terms
            </Link>
            <Link href="/legal/privacy" className="transition hover:text-foreground">
              Privacy
            </Link>
            <Link href="/legal/dpa" className="transition hover:text-foreground">
              DPA
            </Link>
            <Link href="/legal/sla" className="transition hover:text-foreground">
              SLA
            </Link>
            <Link href="/legal/cookies" className="transition hover:text-foreground">
              Cookies
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
