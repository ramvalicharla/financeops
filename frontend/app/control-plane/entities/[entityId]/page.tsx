import { createMetadata } from "@/lib/metadata"
import { ControlPlaneEntitiesPage } from "@/components/control-plane/pages/ControlPlaneEntitiesPage"

export const metadata = createMetadata("Control Plane Entity")

export default async function Page({
  params,
}: {
  params: Promise<{ entityId: string }>
}) {
  const { entityId } = await params
  return <ControlPlaneEntitiesPage entityId={entityId} />
}
