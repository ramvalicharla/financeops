"use client"

import { JobBody } from "@/components/control-plane/bodies/JobBody"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Sheet } from "@/components/ui/Sheet"

export function JobPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)

  return (
    <Sheet
      open={activePanel === "jobs"}
      onClose={closePanel}
      title="Job Panel"
      description="Running, completed, and failed governed jobs."
      width="max-w-2xl"
    >
      <JobBody />
    </Sheet>
  )
}
