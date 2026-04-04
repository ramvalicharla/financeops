import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Anomalies', 'Detect and manage financial anomalies')

export default function Page() {
  return <PageClient />
}
