"use client"

import { useCallback, useState } from "react"
import { Check } from "lucide-react"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Skeleton } from "@/components/ui/skeleton"
import type { UseOrgEntitiesItem } from "@/hooks/useOrgEntities"
import { cn } from "@/lib/utils"

interface EntityCardPickerProps {
  entityId: string | null
  switchEntity: (id: string | null) => void
  entities: UseOrgEntitiesItem[]
  organizationLabel: string
  activeEntityName: string | null
  moduleName: string | null
  contextIsLoading: boolean
}

export function EntityCardPicker({
  entityId,
  switchEntity,
  entities,
  organizationLabel,
  activeEntityName,
  moduleName,
  contextIsLoading,
}: EntityCardPickerProps) {
  const [open, setOpen] = useState(false)

  const handleSelect = useCallback(
    (id: string | null) => {
      switchEntity(id)
      setOpen(false)
    },
    [switchEntity],
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-label="Switch entity"
          className="mt-3 rounded-2xl border border-border bg-background p-4 shadow-sm cursor-pointer hover:bg-accent/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault()
              setOpen(true)
            }
          }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                ACTIVE ENTITY
              </p>
              {contextIsLoading ? (
                <Skeleton className="mt-1 h-5 w-32" />
              ) : (
                <p className="mt-1 text-sm font-semibold text-foreground truncate">
                  {organizationLabel}
                </p>
              )}
            </div>
            <span className="shrink-0 rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Backend
            </span>
          </div>
          <div className="mt-3 space-y-2 rounded-xl border border-border bg-background px-3 py-3 text-sm text-muted-foreground">
            {contextIsLoading ? (
              <>
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-32" />
              </>
            ) : (
              <>
                <p className="truncate">
                  Entity:{" "}
                  {activeEntityName ?? (entityId === null ? "All entities" : "Unavailable")}
                </p>
                <p className="truncate">
                  Workspace: {moduleName ?? "Unavailable"}
                </p>
              </>
            )}
          </div>
        </div>
      </PopoverTrigger>

      <PopoverContent className="w-64 p-0" align="start" side="bottom">
        <Command>
          <CommandInput placeholder="Search entities…" />
          <CommandList>
            <CommandEmpty>No entities found.</CommandEmpty>
            <CommandGroup>
              {/* All entities pseudo-item (OQ-5) */}
              <CommandItem
                value="__all_entities__"
                onSelect={() => handleSelect(null)}
                className={cn(entityId === null && "bg-accent text-accent-foreground")}
              >
                {entityId === null ? (
                  <Check className="mr-2 h-4 w-4 shrink-0" />
                ) : (
                  <span className="mr-2 h-4 w-4 shrink-0 inline-block" />
                )}
                All entities
              </CommandItem>
              {entities.map((entity) => (
                <CommandItem
                  key={entity.entity_id}
                  value={entity.entity_name}
                  onSelect={() => handleSelect(entity.entity_id)}
                  className={cn(
                    entity.entity_id === entityId && "bg-accent text-accent-foreground",
                  )}
                >
                  {entity.entity_id === entityId ? (
                    <Check className="mr-2 h-4 w-4 shrink-0" />
                  ) : (
                    <span className="mr-2 h-4 w-4 shrink-0 inline-block" />
                  )}
                  <span className="truncate">{entity.entity_name}</span>
                  {entity.role ? (
                    <span className="ml-auto pl-2 text-[10px] uppercase tracking-wide text-muted-foreground">
                      {entity.role}
                    </span>
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
