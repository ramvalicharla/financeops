import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Board Pack")

export default function Page() {
  return <PageClient />
}
