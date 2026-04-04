import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Working Capital', 'Working capital analysis and tracking')

export default function Page() {
  return <PageClient />
}
