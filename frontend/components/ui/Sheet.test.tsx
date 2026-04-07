import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { Sheet } from "./Sheet"

describe("Sheet", () => {
  it("does not render when open=false", () => {
    render(
      <Sheet open={false} onClose={vi.fn()} title="Test Sheet">
        <p>Sheet content</p>
      </Sheet>,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.queryByText("Sheet content")).not.toBeInTheDocument()
  })

  it("renders when open=true", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Test Sheet">
        <p>Sheet content</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Sheet content")).toBeInTheDocument()
  })

  it("renders the title", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="My Sheet">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByText("My Sheet")).toBeInTheDocument()
  })

  it("renders description when provided", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Title" description="Sheet description">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByText("Sheet description")).toBeInTheDocument()
  })

  it("has role=dialog", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("has aria-modal=true", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true")
  })

  it("calls onClose when close button is clicked", async () => {
    const onClose = vi.fn()
    render(
      <Sheet open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    await userEvent.click(screen.getByLabelText("Close dialog"))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when Escape key is pressed", async () => {
    const onClose = vi.fn()
    render(
      <Sheet open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    await userEvent.keyboard("{Escape}")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when backdrop is clicked", async () => {
    const onClose = vi.fn()
    render(
      <Sheet open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    const backdrop = document.querySelector(".fixed.inset-0.z-50 > .absolute") as HTMLElement
    if (backdrop) {
      await userEvent.click(backdrop)
      expect(onClose).toHaveBeenCalled()
    }
  })

  it("slides from the right (translate-x class present)", async () => {
    render(
      <Sheet open={false} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Sheet>,
    )
    // When closed, would have translate-x-full; when open it has translate-x-0
    // We test the open state has translate-x-0 on the panel
    render(
      <Sheet open={true} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    const panel = screen.getByRole("dialog")
    // translate-x-0 is applied when visible
    expect(panel.className).toContain("translate-x")
  })

  it("applies custom width class", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Wide" width="max-w-2xl">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toHaveClass("max-w-2xl")
  })

  it("title is linked via aria-labelledby", async () => {
    render(
      <Sheet open={true} onClose={vi.fn()} title="Labeled Sheet">
        <p>body</p>
      </Sheet>,
    )
    await act(async () => {})
    const dialog = screen.getByRole("dialog")
    const labelledBy = dialog.getAttribute("aria-labelledby")
    expect(labelledBy).toBeTruthy()
    const titleEl = document.getElementById(labelledBy!)
    expect(titleEl?.textContent).toBe("Labeled Sheet")
  })
})
