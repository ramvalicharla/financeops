import { createMetadata } from "@/lib/metadata"
import { ControlPlaneJobsPage } from "@/components/control-plane/pages/ControlPlaneJobsPage"

export const metadata = createMetadata("Control Plane Job")

export default async function Page({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  const { jobId } = await params
  return <ControlPlaneJobsPage jobId={jobId} />
}
