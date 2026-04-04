import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Scheduled Delivery', 'Manage automated report delivery')

export default function Page() {
  return <PageClient />
}
