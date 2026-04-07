import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Scenario")

export default function Page() {
  return <PageClient />
}
