import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"

export default async function DashboardPage() {
  const session = await auth()
  if (!session?.user) {
    redirect("/login")
  }

  const role = session.user.role
  if (role === "platform_owner" || role === "super_admin") {
    redirect("/admin")
  }
  if (role === "director") {
    redirect("/dashboard/director")
  }
  if (role === "auditor") {
    redirect("/audit")
  }
  if (role === "read_only") {
    redirect("/reports")
  }

  redirect("/mis")
}
