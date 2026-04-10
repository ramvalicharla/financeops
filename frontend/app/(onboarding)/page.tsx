import { createMetadata } from "@/lib/metadata"
import { OnboardingWizard } from "@/components/onboarding/OnboardingWizard"

export const metadata = createMetadata("Onboarding")

export default function OnboardingPage() {
  return <OnboardingWizard />
}
