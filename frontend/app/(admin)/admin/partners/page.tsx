import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Partners")

export default function Page() {
  return <PageClient />
}
