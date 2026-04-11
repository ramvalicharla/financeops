import { createMetadata } from "@/lib/metadata"
import { ControlPlaneAirlockPage } from "@/components/control-plane/pages/ControlPlaneAirlockPage"

export const metadata = createMetadata("Control Plane Airlock Item")

export default async function Page({
  params,
}: {
  params: Promise<{ itemId: string }>
}) {
  const { itemId } = await params
  return <ControlPlaneAirlockPage itemId={itemId} />
}
