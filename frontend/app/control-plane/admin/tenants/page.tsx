import { createMetadata } from "@/lib/metadata"
import { AdminTenantsPageClient } from "./PageClient"

export const metadata = createMetadata("Tenants — Platform Admin")

export default function Page() {
  return <AdminTenantsPageClient />
}
