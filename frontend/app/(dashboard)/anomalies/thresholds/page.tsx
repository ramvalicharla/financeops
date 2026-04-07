import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Anomaly Thresholds")

export default function Page() {
  return <PageClient />
}
