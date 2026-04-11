import { createMetadata } from "@/lib/metadata"
import { ControlPlaneIntentsPage } from "@/components/control-plane/pages/ControlPlaneIntentsPage"

export const metadata = createMetadata("Control Plane Intent")

export default async function Page({
  params,
}: {
  params: Promise<{ intentId: string }>
}) {
  const { intentId } = await params
  return <ControlPlaneIntentsPage intentId={intentId} />
}
