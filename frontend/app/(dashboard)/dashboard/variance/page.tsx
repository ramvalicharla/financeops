import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Variance")

export default function Page() {
  return <PageClient />
}
