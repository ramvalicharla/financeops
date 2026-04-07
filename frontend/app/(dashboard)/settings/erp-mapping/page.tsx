import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("ERP Mapping")

export default function Page() {
  return <PageClient />
}
