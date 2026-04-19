import type { Metadata } from "next"
import { Topbar } from "@/components/layout/Topbar"
import PageClient from "./PageClient"

export const metadata: Metadata = {
  title: "Global Search | Finqor",
}

export default function GlobalSearchPage() {
  return (
    <div className="flex h-full w-full flex-col bg-background">
      <Topbar
        tenantSlug="financeops"
        userName="Admin User"
        userEmail="admin@financeops.com"
        entityRoles={[]}
      />
      <main id="main-content" className="flex-1 overflow-y-auto outline-none">
        <PageClient />
      </main>
    </div>
  )
}
