import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Statutory")

export default function Page() {
  return <PageClient />
}
