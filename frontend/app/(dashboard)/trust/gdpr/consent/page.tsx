import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("GDPR Consent")

export default function Page() {
  return <PageClient />
}
