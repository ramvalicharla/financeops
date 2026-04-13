import { createMetadata } from "@/lib/metadata"
import HomePageClient from "./HomePageClient"

export const metadata = createMetadata(
  "Dashboard",
  "Today's focus — an overview of your workspace",
)

export default function DashboardRootPage() {
  return <HomePageClient />
}
