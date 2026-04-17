import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("New Journal")

export default function Page() {
  return <PageClient />
}
