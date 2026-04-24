import { createMetadata } from "@/lib/metadata"
import { AdminTenantDetailPageClient } from "./PageClient"

export const metadata = createMetadata("Tenant Detail — Platform Admin")

export default function Page() {
  return <AdminTenantDetailPageClient />
}
