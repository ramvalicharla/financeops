import PageClient from "./PageClient"
import { createMetadata } from "@/lib/metadata"
export const metadata = createMetadata("Balance Sheet")
export default function Page() { return <PageClient /> }
