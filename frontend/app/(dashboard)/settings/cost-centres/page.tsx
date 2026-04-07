import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("Cost Centres")

export default function Page() {
  return <PageClient />
}
