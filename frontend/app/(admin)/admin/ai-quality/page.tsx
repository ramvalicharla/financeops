import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("AI Quality")

export default function Page() {
  return <PageClient />
}
