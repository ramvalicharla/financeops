import type { Metadata } from "next"
import { SettingsControlPlaneClient } from "./SettingsControlPlaneClient"

export const metadata: Metadata = {
  title: "Control Plane Settings · Finqor",
  description: "Determinism, timeline, and lineage configuration for the platform control plane.",
}

export default function ControlPlaneSettingsPage() {
  return <SettingsControlPlaneClient />
}
