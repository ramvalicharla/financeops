import { createMetadata } from "@/lib/metadata"
import { AdminCreditsPageClient } from "./PageClient"

export const metadata = createMetadata("Credits — Platform Admin")

export default function Page() {
  return <AdminCreditsPageClient />
}
