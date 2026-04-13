import { createMetadata } from "@/lib/metadata"
import PageClient from "./PageClient"

export const metadata = createMetadata(
  "Choose Organisation",
  "Select the workspace you want to enter",
)

export default function Page() {
  return <PageClient />
}
