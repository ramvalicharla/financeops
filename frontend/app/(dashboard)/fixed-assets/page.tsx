import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata('Fixed Assets', 'Fixed asset register and depreciation')

export default function Page() {
  return <PageClient />
}
