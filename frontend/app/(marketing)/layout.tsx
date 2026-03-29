import type { ReactNode } from "react"

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <nav className="flex items-center justify-between border-b border-gray-800 px-8 py-5">
        <span className="text-xl font-bold text-white">FinanceOps</span>
        <div className="flex items-center gap-4">
          <a href="/login" className="text-sm text-gray-400 hover:text-white">
            Sign in
          </a>
          <a
            href="/register"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium hover:bg-blue-700"
          >
            Start free trial
          </a>
        </div>
      </nav>
      <main>{children}</main>
      <footer className="flex items-center justify-between border-t border-gray-800 px-8 py-6 text-sm text-gray-500">
        <span>(c) 2026 FinanceOps. All rights reserved.</span>
        <div className="flex gap-6">
          <a href="/legal/terms" className="hover:text-gray-300">
            Terms
          </a>
          <a href="/legal/privacy" className="hover:text-gray-300">
            Privacy
          </a>
          <a href="/legal/dpa" className="hover:text-gray-300">
            DPA
          </a>
          <a href="/legal/sla" className="hover:text-gray-300">
            SLA
          </a>
          <a href="/legal/cookies" className="hover:text-gray-300">
            Cookies
          </a>
        </div>
      </footer>
    </div>
  )
}

