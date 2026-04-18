import PageClient from "./PageClient"
import { createMetadata } from "@/lib/metadata"
export const metadata = createMetadata("Cash Flow Statement")
export default function Page() { return <PageClient /> }
