import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata("SOC 2")

export default function Page() {
  return <PageClient />
}
