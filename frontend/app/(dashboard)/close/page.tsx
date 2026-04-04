import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Period Close', 'Manage financial period close workflows')

export default function Page() {
  return <PageClient />
}
