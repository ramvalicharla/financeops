import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { StepIndicator } from "./StepIndicator"

// ORG_SETUP_STEP_NAMES has 4 steps
const ORG_TOTAL = 4

describe("StepIndicator — onboarding variant (currentStep prop)", () => {
  it("renders the correct number of step bars", () => {
    const { container } = render(<StepIndicator currentStep={1} totalSteps={5} />)
    // Each step is a div inside the flex container
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

describe("StepIndicator — org-setup variant (step prop)", () => {
  it("renders step and total in the text", () => {
    render(<StepIndicator step={1} />)
    expect(screen.getByText(/Step 1 of/)).toBeInTheDocument()
  })

  it("renders the step name from ORG_SETUP_STEP_NAMES", () => {
    render(<StepIndicator step={1} />)
    // First step name is "Group identity"
    expect(screen.getByText("Group identity")).toBeInTheDocument()
  })

  it("renders step 2 name", () => {
    render(<StepIndicator step={2} />)
    expect(screen.getByText("Legal entities")).toBeInTheDocument()
  })

  it("clamps step below minimum to 1", () => {
    render(<StepIndicator step={0} />)
    expect(screen.getByText(/Step 1 of/)).toBeInTheDocument()
  })

  it("clamps step above maximum to totalSteps", () => {
    render(<StepIndicator step={99} />)
    expect(screen.getByText(new RegExp(`Step ${ORG_TOTAL} of`))).toBeInTheDocument()
  })

  it("renders a progress bar element", () => {
    const { container } = render(<StepIndicator step={2} />)
    // The progress bar div has an inline width style
    const bar = container.querySelector("[style]")
    expect(bar).toBeInTheDocument()
  })

  it("progress bar width reflects step fraction", () => {
    const { container } = render(<StepIndicator step={2} />)
    const bar = container.querySelector("[style]") as HTMLElement
    const expectedPct = ((2 / ORG_TOTAL) * 100).toFixed(0)
    expect(bar.style.width).toContain(expectedPct)
  })
})
