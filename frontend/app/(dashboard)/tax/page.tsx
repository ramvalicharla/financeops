import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Tax', 'Tax provision and compliance')

export default function Page() {
  return <PageClient />
}
