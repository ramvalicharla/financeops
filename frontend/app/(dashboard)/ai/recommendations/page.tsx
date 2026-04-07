import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("AI Recommendations")

export default function Page() {
  return <PageClient />
}
