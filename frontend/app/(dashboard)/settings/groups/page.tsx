import { redirect } from "next/navigation"

export default function GroupsPage() {
  redirect("/settings/team?tab=groups")
}
