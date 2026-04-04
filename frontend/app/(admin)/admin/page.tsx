import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Admin", "System administration and tenant management")

export default function Page() {
  return <PageClient />
}
