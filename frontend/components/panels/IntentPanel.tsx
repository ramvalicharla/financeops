"use client"

import { IntentBody } from "@/components/control-plane/bodies/IntentBody"
import { useControlPlaneStore } from "@/lib/store/controlPlane"
import { Sheet } from "@/components/ui/Sheet"

export function IntentPanel() {
  const activePanel = useControlPlaneStore((state) => state.active_panel)
  const closePanel = useControlPlaneStore((state) => state.closePanel)

  return (
    <Sheet
      open={activePanel === "intent"}
      onClose={closePanel}
      title="Intent Panel"
      description="Backend-returned intent details for the selected governed action."
      width="max-w-xl"
    >
      <IntentBody />
    </Sheet>
  )
}
