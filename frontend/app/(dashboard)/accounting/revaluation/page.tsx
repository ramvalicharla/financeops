import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Revaluation")

export default function Page() {
  return <PageClient />
}
