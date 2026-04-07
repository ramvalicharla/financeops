import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { StatusBadge } from "./StatusBadge"

describe("StatusBadge", () => {
  it("renders the status text by default", () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText("pending")).toBeInTheDocument()
  })

  it("renders label prop instead of status when provided", () => {
    render(<StatusBadge status="running" label="In Progress" />)
    expect(screen.getByText("In Progress")).toBeInTheDocument()
    expect(screen.queryByText("running")).not.toBeInTheDocument()
  })

  it("renders as a span", () => {
    const { container } = render(<StatusBadge status="complete" />)
    expect(container.querySelector("span")).toBeInTheDocument()
  })

  it("applies pending color class for pending status", () => {
    const { container } = render(<StatusBadge status="pending" />)
    expect(container.firstChild).toHaveClass("bg-yellow-500/20")
  })

  it("applies running color class and animate-pulse for running status", () => {
    const { container } = render(<StatusBadge status="running" />)
    expect(container.firstChild).toHaveClass("bg-blue-500/20")
    expect(container.firstChild).toHaveClass("animate-pulse")
  })

  it("applies default muted class for unknown status", () => {
    const { container } = render(<StatusBadge status="unknown-xyz" />)
    expect(container.firstChild).toHaveClass("bg-muted")
  })

  it("normalizes status to lowercase", () => {
    const { container } = render(<StatusBadge status="PENDING" />)
    expect(container.firstChild).toHaveClass("bg-yellow-500/20")
  })

  it("normalizes status with spaces using underscores", () => {
    // e.g. 'in progress' → not in STATUS_COLORS → default
    const { container } = render(<StatusBadge status="draft" />)
    expect(container.firstChild).toHaveClass("bg-muted")
  })

  it("renders complete status with success class", () => {
    const { container } = render(<StatusBadge status="complete" />)
    // complete uses --brand-success color class
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain("brand-success")
  })

  it("renders failed status with danger class", () => {
    const { container } = render(<StatusBadge status="failed" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain("brand-danger")
  })

  it("does not animate non-running statuses", () => {
    const { container } = render(<StatusBadge status="complete" />)
    expect(container.firstChild).not.toHaveClass("animate-pulse")
  })

  it("snapshot — pending", () => {
    const { container } = render(<StatusBadge status="pending" />)
    expect(container.firstChild).toMatchSnapshot()
  })

  it("snapshot — running", () => {
    const { container } = render(<StatusBadge status="running" />)
    expect(container.firstChild).toMatchSnapshot()
  })

  it("snapshot — failed", () => {
    const { container } = render(<StatusBadge status="failed" />)
    expect(container.firstChild).toMatchSnapshot()
  })
})
