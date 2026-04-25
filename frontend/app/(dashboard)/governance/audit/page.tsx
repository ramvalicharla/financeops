import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Audit Access', 'Manage external auditor access')

export default function Page() {
  return <PageClient />
}
