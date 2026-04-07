import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Revenue Module")

export default function Page() {
  return <PageClient />
}
