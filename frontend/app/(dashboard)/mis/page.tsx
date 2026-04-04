import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('MIS', 'Management information and analytics')

export default function Page() {
  return <PageClient />
}
