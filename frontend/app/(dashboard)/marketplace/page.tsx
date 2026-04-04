import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Marketplace', 'Financial templates and integrations')

export default function Page() {
  return <PageClient />
}
