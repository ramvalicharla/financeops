import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Consolidation Run")

export default function Page() {
  return <PageClient />
}
