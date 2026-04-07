import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("GDPR Breach")

export default function Page() {
  return <PageClient />
}
