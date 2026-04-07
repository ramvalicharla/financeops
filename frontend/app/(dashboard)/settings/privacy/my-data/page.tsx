import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("My Data")

export default function Page() {
  return <PageClient />
}
