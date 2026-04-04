import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Consolidation', 'Group consolidation and elimination')

export default function Page() {
  return <PageClient />
}
