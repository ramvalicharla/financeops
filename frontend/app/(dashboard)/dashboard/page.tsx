import { redirect } from "next/navigation"
import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Dashboard")

export default function DashboardRootPage() {
  redirect("/dashboard/cfo")
}

