import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Reports', 'Generate and manage financial reports')

export default function Page() {
  return <PageClient />
}
