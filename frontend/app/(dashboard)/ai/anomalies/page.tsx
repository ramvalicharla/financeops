import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("AI Anomalies")

export default function Page() {
  return <PageClient />
}
