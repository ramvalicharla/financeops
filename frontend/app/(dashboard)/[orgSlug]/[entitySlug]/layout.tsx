"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import { useTenantStore } from "@/lib/store/tenant"

interface OrgEntityLayoutProps {
  children: React.ReactNode
  params: {
    orgSlug: string
    entitySlug: string
  }
}

export default function OrgEntityLayout({ children, params }: OrgEntityLayoutProps) {
  const { orgSlug, entitySlug } = params
  const setActiveEntity = useTenantStore((state) => state.setActiveEntity)

  // Hydrate the URL slugs into our global store so API Interceptors function passively
  useEffect(() => {
    if (entitySlug) {
      setActiveEntity(entitySlug)
    }
  }, [entitySlug, setActiveEntity])

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
