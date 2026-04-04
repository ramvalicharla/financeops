import type { ReactNode } from "react"
import { headers } from "next/headers"
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import { AdminSidebar } from "@/components/admin/AdminSidebar"

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const requestHeaders = headers()
  const isE2EBypass =
    process.env.NODE_ENV !== "production" &&
    requestHeaders.get("x-e2e-auth-bypass") === "true"

  const session = await auth()
  const role = session?.user?.role ?? ""
  const allowed = ["platform_owner", "platform_admin", "super_admin", "admin"]

  if (!isE2EBypass && (!session?.user || !allowed.includes(role))) {
    redirect("/dashboard")
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <AdminSidebar />
      <main id="main-content" className="p-6 md:pl-72">{children}</main>
    </div>
  )
}
