import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("PPA")

export default function Page() {
  return <PageClient />
}
