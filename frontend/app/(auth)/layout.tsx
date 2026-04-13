import type { ReactNode } from "react"
import { ValueProps } from "./components/ValueProps"

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_480px]">
      {/* Left brand panel — hidden on mobile */}
      <div className="hidden lg:flex flex-col items-center justify-center bg-muted/30 border-r border-border p-12">
        <div className="max-w-sm text-center space-y-6">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mx-auto">
            <span className="text-primary-foreground font-semibold text-lg">F</span>
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold">Built for finance teams</h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              IFRS-compliant, audit-ready, and connected to 23 ERPs. Trusted by CFOs across India.
            </p>
          </div>
          <ValueProps />
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex items-center justify-center p-8">
        {children}
      </div>
    </div>
  )
}
