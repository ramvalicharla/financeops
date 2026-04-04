import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Budget', 'Budget planning and variance analysis')

export default function Page() {
  return <PageClient />
}
