"use client"

import { useEffect } from "react"
import { useWorkspaceStore } from "@/lib/store/workspace"

interface OrgEntityLayoutProps {
  children: React.ReactNode
  params: {
    orgSlug: string
    entitySlug: string
  }
}

export default function OrgEntityLayout({ children, params }: OrgEntityLayoutProps) {
  const { orgSlug, entitySlug } = params
  const switchEntity = useWorkspaceStore((s) => s.switchEntity)
  const setOrgId = useWorkspaceStore((s) => s.setOrgId)

  // Hydrate URL slugs into workspaceStore so API interceptors pick up the
  // correct entity context passively.
  useEffect(() => {
    if (orgSlug) setOrgId(orgSlug)
    if (entitySlug) switchEntity(entitySlug)
  }, [entitySlug, orgSlug, setOrgId, switchEntity])

  return (
    <div className="flex flex-col h-full w-full animate-in fade-in duration-300">
      {/*
        Future: Place specific Entity-level context bars or
        Module Tabs here that should persist across all inside pages!
      */}
      <div className="flex-1 w-full relative">
        {children}
      </div>
    </div>
  )
}
