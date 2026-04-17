"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import {
  Calculator,
  Calendar,
  CreditCard,
  Settings,
  Smile,
  User,
  Search,
  Building,
  Activity,
  FileBarChart,
  RefreshCw
} from "lucide-react"

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { useTenantStore } from "@/lib/store/tenant"

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const router = useRouter()
  
  const orgSlug = useTenantStore((state) => state.tenant_slug)
  const entitySlug = useTenantStore((state) => state.active_entity_id)

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((open) => !open)
      }
    }

    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  const runCommand = (command: () => void) => {
    setOpen(false)
    command()
  }

  const navigateTo = (href: string, requiresContext = false) => {
    runCommand(() => {
      if (requiresContext && orgSlug && entitySlug) {
        router.push(`/${orgSlug}/${entitySlug}${href}`)
      } else {
        router.push(href)
      }
    })
  }

  return (
    <>
      {/* 
        Optional trigger button that can be rendered in the top nav
        <button onClick={() => setOpen(true)}>Search (Cmd K)</button>
      */}
      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Platform Operations">
            <CommandItem onSelect={() => navigateTo("/settings", false)}>
              <Settings className="mr-2 h-4 w-4" />
              <span>Global Settings</span>
            </CommandItem>
            <CommandItem onSelect={() => navigateTo("/billing", false)}>
              <CreditCard className="mr-2 h-4 w-4" />
              <span>Billing</span>
            </CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Active Entity Context">
            <CommandItem onSelect={() => navigateTo("/accounting/journals", true)}>
              <FileBarChart className="mr-2 h-4 w-4" />
              <span>Ledger & Journals</span>
              <CommandShortcut>J</CommandShortcut>
            </CommandItem>
            <CommandItem onSelect={() => navigateTo("/accounting/trial-balance", true)}>
              <Calculator className="mr-2 h-4 w-4" />
              <span>Trial Balance</span>
            </CommandItem>
            <CommandItem onSelect={() => navigateTo("/settings/integrations/erp", true)}>
              <RefreshCw className="mr-2 h-4 w-4" />
              <span>ERP Connectivity</span>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  )
}
