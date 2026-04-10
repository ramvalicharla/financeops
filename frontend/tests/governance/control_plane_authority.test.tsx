import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { FlowStrip } from "@/components/ui/FlowStrip"

describe("control plane authority guardrails", () => {
  it("keeps FlowStrip purely prop-driven", () => {
    render(
      <FlowStrip
        title="Example flow"
        subtitle="Pure renderer"
        steps={[
          { label: "Upload", tone: "active" },
          { label: "Airlock", tone: "default" },
        ]}
      />,
    )

    expect(screen.getByText("Upload")).toBeInTheDocument()
    expect(screen.getByText("Airlock")).toBeInTheDocument()
    expect(screen.queryByText("Complete")).not.toBeInTheDocument()
  })
})
