import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ORG_SETUP_STEP_NAMES } from "@/components/org-setup/constants"

import { StepIndicator } from "./StepIndicator"

const ORG_TOTAL = ORG_SETUP_STEP_NAMES.length

describe("StepIndicator - onboarding variant (currentStep prop)", () => {
  it("renders the correct number of step bars", () => {
    const { container } = render(<StepIndicator currentStep={1} totalSteps={5} />)
    const bars = container.querySelectorAll('[title^="Step"]')
    expect(bars).toHaveLength(5)
  })

  it("uses default totalSteps=5 when not specified", () => {
    const { container } = render(<StepIndicator currentStep={1} />)
    const bars = container.querySelectorAll('[title^="Step"]')
    expect(bars).toHaveLength(5)
  })

  it("has aria-label on the container", () => {
    render(<StepIndicator currentStep={2} totalSteps={3} />)
    expect(screen.getByLabelText("Onboarding steps")).toBeInTheDocument()
  })

  it("active step has brand-primary class", () => {
    const { container } = render(<StepIndicator currentStep={2} totalSteps={3} />)
    const bars = container.querySelectorAll('[title^="Step"]')
    expect(bars[1]).toHaveClass("bg-[hsl(var(--brand-primary))]")
  })

  it("completed steps have brand-success class", () => {
    const { container } = render(<StepIndicator currentStep={3} totalSteps={3} />)
    const bars = container.querySelectorAll('[title^="Step"]')
    expect(bars[0]).toHaveClass("bg-[hsl(var(--brand-success))]")
    expect(bars[1]).toHaveClass("bg-[hsl(var(--brand-success))]")
  })

  it("future steps have muted class", () => {
    const { container } = render(<StepIndicator currentStep={1} totalSteps={3} />)
    const bars = container.querySelectorAll('[title^="Step"]')
    expect(bars[1]).toHaveClass("bg-muted")
    expect(bars[2]).toHaveClass("bg-muted")
  })

  it("only the current step bar has brand-primary", () => {
    const { container } = render(<StepIndicator currentStep={2} totalSteps={4} />)
    const primaryBars = container.querySelectorAll(".bg-\\[hsl\\(var\\(--brand-primary\\)\\)\\]")
    expect(primaryBars).toHaveLength(1)
  })
})

describe("StepIndicator - org-setup variant (step prop)", () => {
  it("renders the setup progress list", () => {
    render(<StepIndicator step={1} />)
    expect(screen.getByLabelText("Setup progress")).toBeInTheDocument()
  })

  it("renders the step name from ORG_SETUP_STEP_NAMES", () => {
    render(<StepIndicator step={1} />)
    expect(screen.getByText(ORG_SETUP_STEP_NAMES[0])).toBeInTheDocument()
  })

  it("renders step 2 name", () => {
    render(<StepIndicator step={2} />)
    expect(screen.getByText(ORG_SETUP_STEP_NAMES[1])).toBeInTheDocument()
  })

  it("clamps step below minimum to 1", () => {
    const { container } = render(<StepIndicator step={0} />)
    const active = container.querySelector(".ring-1")
    expect(active).toBeInTheDocument()
    expect(active).toHaveTextContent(ORG_SETUP_STEP_NAMES[0])
  })

  it("clamps step above maximum to totalSteps", () => {
    const { container } = render(<StepIndicator step={99} />)
    const active = container.querySelector(".ring-1")
    expect(active).toBeInTheDocument()
    expect(active).toHaveTextContent(ORG_SETUP_STEP_NAMES[ORG_TOTAL - 1])
  })

  it("renders all org setup steps", () => {
    const { container } = render(<StepIndicator step={2} />)
    const items = container.querySelectorAll("ol[aria-label='Setup progress'] > li")
    expect(items).toHaveLength(ORG_TOTAL)
  })

  it("marks completed and active steps correctly", () => {
    const { container } = render(<StepIndicator step={2} />)
    const items = Array.from(container.querySelectorAll("li"))
    const completed = items.find((item) => item.textContent?.includes(ORG_SETUP_STEP_NAMES[0]))
    const active = container.querySelector(".ring-1")
    expect(completed?.querySelector("svg")).toBeInTheDocument()
    expect(active).toHaveTextContent(ORG_SETUP_STEP_NAMES[1])
  })
})
