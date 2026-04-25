import type { Metadata } from "next"
import { TeamPageClient } from "./TeamPageClient"

export const metadata: Metadata = {
  title: "Team · Finqor",
  description: "Manage team members, roles, and groups for your organisation.",
}

interface PageProps {
  searchParams: { tab?: string }
}

export default function TeamPage({ searchParams }: PageProps) {
  return <TeamPageClient initialTab={searchParams.tab === "groups" ? "groups" : "users"} />
}
