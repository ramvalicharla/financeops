"use client"

import { useMemo, useState } from "react"
import { Check, ChevronsUpDown } from "lucide-react"
import { useWorkspaceStore } from "@/lib/store/workspace"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { cn } from "@/lib/utils"

type EntitySwitcherOption = {
  entity_id: string
  entity_name: string
  role?: "admin" | "accountant" | "auditor" | "viewer" | null
}

const roleLabelMap: Record<NonNullable<EntitySwitcherOption["role"]>, string> = {
  admin: "Admin",
  accountant: "Accountant",
  auditor: "Auditor",
  viewer: "Viewer",
}

const roleStyles: Record<NonNullable<EntitySwitcherOption["role"]>, string> = {
  admin: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  accountant: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  auditor: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  viewer: "bg-muted text-muted-foreground",
}

function RoleBadge({ role }: { role?: EntitySwitcherOption["role"] }) {
  if (!role) return null
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-medium",
        roleStyles[role],
      )}
    >
      {roleLabelMap[role]}
    </span>
  )
}

interface EntitySwitcherProps {
  entityRoles: EntitySwitcherOption[]
}

export function EntitySwitcher({ entityRoles }: EntitySwitcherProps) {
  const activeEntityId = useWorkspaceStore((s) => s.entityId)
  const switchEntity = useWorkspaceStore((s) => s.switchEntity)
  const [open, setOpen] = useState(false)

  const activeEntity = useMemo(
    () => entityRoles.find((e) => e.entity_id === activeEntityId) ?? entityRoles[0] ?? null,
    [activeEntityId, entityRoles],
  )

  if (!entityRoles.length) {
    return (
      <span className="text-xs text-muted-foreground">No entity access</span>
    )
  }

  // Single entity — no switcher needed, just show the name
  if (entityRoles.length === 1) {
    return (
      <span className="text-sm font-medium text-foreground">
        {activeEntity?.entity_name}
      </span>
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 font-normal"
          aria-label="Switch active entity"
          aria-expanded={open}
        >
          <span className="max-w-[160px] truncate text-sm font-medium">
            {activeEntity?.entity_name ?? "Select entity"}
          </span>
          <RoleBadge role={activeEntity?.role} />
          <ChevronsUpDown size={12} className="shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Search entities..." />
          <CommandList>
            <CommandEmpty>No entities found.</CommandEmpty>
            <CommandGroup>
              {entityRoles.map((entity) => (
                <CommandItem
                  key={entity.entity_id}
                  value={entity.entity_name}
                  onSelect={() => {
                    switchEntity(entity.entity_id)
                    setOpen(false)
                  }}
                >
                  <div className="flex min-w-0 flex-1 items-center justify-between">
                    <span className="truncate">{entity.entity_name}</span>
                    <RoleBadge role={entity.role} />
                  </div>
                  {entity.entity_id === activeEntityId ? (
                    <Check size={14} className="ml-2 shrink-0 text-primary" />
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
