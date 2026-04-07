import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Privacy Consent")

export default function Page() {
  return <PageClient />
}
