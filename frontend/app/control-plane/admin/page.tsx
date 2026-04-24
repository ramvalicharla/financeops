import { createMetadata } from "@/lib/metadata"
import { AdminDashboardPageClient } from "./PageClient"

export const metadata = createMetadata("Platform Admin")

export default function Page() {
  return <AdminDashboardPageClient />
}
