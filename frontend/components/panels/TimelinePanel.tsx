"use client"

import { TimelineBody } from "@/components/control-plane/bodies/TimelineBody"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Sheet } from "@/components/ui/Sheet"

export function TimelinePanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)

  return (
    <Sheet
      open={activePanel === "timeline"}
      onClose={closePanel}
      title="Timeline"
      description="Chronological event drawer for the selected control-plane scope."
      width="max-w-3xl"
    >
      <TimelineBody />
    </Sheet>
  )
}
