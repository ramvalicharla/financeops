import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Treasury', 'Cash and treasury management')

export default function Page() {
  return <PageClient />
}
