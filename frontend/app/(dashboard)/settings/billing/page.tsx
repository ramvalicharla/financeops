import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Billing")

export default function Page() {
  return <PageClient />
}
