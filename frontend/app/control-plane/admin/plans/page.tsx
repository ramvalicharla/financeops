import { createMetadata } from "@/lib/metadata"
import { AdminPlansPageClient } from "./PageClient"

export const metadata = createMetadata("Plans — Platform Admin")

export default function Page() {
  return <AdminPlansPageClient />
}
