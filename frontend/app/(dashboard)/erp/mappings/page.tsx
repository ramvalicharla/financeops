import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("ERP Mappings")

export default function Page() {
  return <PageClient />
}
