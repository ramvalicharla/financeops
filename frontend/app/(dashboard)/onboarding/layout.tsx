import type { ReactNode } from "react"

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-5xl">{children}</div>
}
