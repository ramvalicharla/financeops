"use client"

import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UsersPanel } from "./_components/UsersPanel"
import { GroupsPanel } from "./_components/GroupsPanel"

interface TeamPageClientProps {
  initialTab: "users" | "groups"
}

export function TeamPageClient({ initialTab }: TeamPageClientProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [tab, setTab] = useState<"users" | "groups">(initialTab)

  const handleTabChange = (next: string) => {
    if (next !== "users" && next !== "groups") return
    setTab(next)
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", next)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-xl font-medium">Team</h1>
        <p className="text-sm text-muted-foreground">
          Manage team members, roles, and groups for your organisation.
        </p>
      </header>
      <Tabs value={tab} onValueChange={handleTabChange} className="flex flex-1 flex-col">
        <TabsList className="border-b border-border bg-transparent px-6 rounded-none h-10 justify-start">
          <TabsTrigger
            value="users"
            className="data-[state=active]:border-b-2 data-[state=active]:border-[#185FA5] data-[state=active]:bg-transparent data-[state=active]:font-medium data-[state=active]:text-foreground rounded-none border-b-2 border-transparent text-muted-foreground transition-colors"
          >
            Users
          </TabsTrigger>
          <TabsTrigger
            value="groups"
            className="data-[state=active]:border-b-2 data-[state=active]:border-[#185FA5] data-[state=active]:bg-transparent data-[state=active]:font-medium data-[state=active]:text-foreground rounded-none border-b-2 border-transparent text-muted-foreground transition-colors"
          >
            Groups
          </TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="flex-1 overflow-auto mt-0">
          <UsersPanel />
        </TabsContent>
        <TabsContent value="groups" className="flex-1 overflow-auto mt-0">
          <GroupsPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
