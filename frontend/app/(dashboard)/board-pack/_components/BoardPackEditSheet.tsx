"use client"

import { Loader2 } from "lucide-react"
import { Sheet } from "@/components/ui/Sheet"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { allSectionTypes, type EditDefinitionState } from "../_hooks/useBoardPack"
import { SectionType } from "@/lib/types/board-pack"

interface BoardPackEditSheetProps {
  editState: EditDefinitionState | null
  onAddEntityId: () => void
  onClose: () => void
  onRemoveEntityId: (entityId: string) => void
  onSave: () => void
  onSetValue: (updates: Partial<EditDefinitionState>) => void
  onToggleSectionType: (sectionType: SectionType, checked: boolean) => void
}

export function BoardPackEditSheet({
  editState,
  onAddEntityId,
  onClose,
  onRemoveEntityId,
  onSave,
  onSetValue,
  onToggleSectionType,
}: BoardPackEditSheetProps) {
  return (
    <Sheet
      open={Boolean(editState)}
      onClose={editState?.saving ? () => undefined : onClose}
      title="Edit Definition"
      width="max-w-xl"
    >
      {editState ? (
        <div className="space-y-4">
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="edit-name">
              Name
            </label>
            <Input
              id="edit-name"
              value={editState.name}
              onChange={(event) => onSetValue({ name: event.target.value })}
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="edit-description">
              Description
            </label>
            <textarea
              id="edit-description"
              className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={editState.description}
              onChange={(event) => onSetValue({ description: event.target.value })}
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm text-foreground">Section Types</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {allSectionTypes.map((sectionType) => {
                const checked = editState.sectionTypes.includes(sectionType)
                return (
                  <label
                    key={sectionType}
                    className="flex items-center gap-2 rounded-md border border-border px-2 py-1.5 text-sm text-muted-foreground"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) =>
                        onToggleSectionType(sectionType, event.target.checked)
                      }
                    />
                    {sectionType}
                  </label>
                )
              })}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm text-foreground">Entity IDs</p>
            <div className="flex gap-2">
              <Input
                placeholder="Add entity UUID"
                value={editState.newEntityId}
                onChange={(event) => onSetValue({ newEntityId: event.target.value })}
              />
              <Button type="button" variant="outline" onClick={onAddEntityId}>
                Add
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {editState.entityIds.map((entityId) => (
                <span
                  key={entityId}
                  className="inline-flex items-center gap-2 rounded-full border border-border px-2 py-1 text-xs text-muted-foreground"
                >
                  {entityId}
                  <button
                    type="button"
                    className="text-foreground"
                    onClick={() => onRemoveEntityId(entityId)}
                    aria-label={`Remove ${entityId}`}
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm text-foreground" htmlFor="edit-config">
              Config (JSON)
            </label>
            <textarea
              id="edit-config"
              className="min-h-40 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs text-foreground"
              value={editState.configText}
              onChange={(event) => onSetValue({ configText: event.target.value })}
            />
          </div>

          {editState.error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {editState.error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={editState.saving}
            >
              Cancel
            </Button>
            <Button type="button" onClick={onSave} disabled={editState.saving}>
              {editState.saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save"
              )}
            </Button>
          </div>
        </div>
      ) : null}
    </Sheet>
  )
}
