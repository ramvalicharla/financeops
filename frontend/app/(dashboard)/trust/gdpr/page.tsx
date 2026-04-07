import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("GDPR")

export default function Page() {
  return <PageClient />
}
