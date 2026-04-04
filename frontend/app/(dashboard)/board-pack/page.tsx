import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Board Pack', 'Prepare and distribute board packs')

export default function Page() {
  return <PageClient />
}
