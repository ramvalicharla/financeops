import { createMetadata } from "@/lib/metadata"
import { LimitedControlPlanePage } from "@/components/control-plane/pages/LimitedControlPlanePage"

export const metadata = createMetadata("Control Plane Admin")

export default function Page() {
  return (
    <LimitedControlPlanePage
      title="Admin"
      description="Administrative control-plane capabilities are intentionally limited in this phase."
      body="Admin control plane limited. Use the existing platform admin surfaces for capabilities that are not exposed through the current control-plane contract."
    />
  )
}
