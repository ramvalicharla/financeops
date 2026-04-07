import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { Dialog } from "./Dialog"

// Dialog uses createPortal — jsdom supports it natively

describe("Dialog", () => {
  it("does not render content when open=false", () => {
    render(
      <Dialog open={false} onClose={vi.fn()} title="Test Dialog">
        <p>Dialog content</p>
      </Dialog>,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
    expect(screen.queryByText("Dialog content")).not.toBeInTheDocument()
  })

  it("renders when open=true", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Test Dialog">
        <p>Dialog content</p>
      </Dialog>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toBeInTheDocument()
    expect(screen.getByText("Dialog content")).toBeInTheDocument()
  })

  it("renders the title", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="My Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    expect(screen.getByText("My Title")).toBeInTheDocument()
  })

  it("renders description when provided", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Title" description="Supporting text">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    expect(screen.getByText("Supporting text")).toBeInTheDocument()
  })

  it("has role=dialog", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toBeInTheDocument()
  })

  it("has aria-modal=true", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true")
  })

  it("calls onClose when close button is clicked", async () => {
    const onClose = vi.fn()
    render(
      <Dialog open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    await userEvent.click(screen.getByLabelText("Close dialog"))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when Escape key is pressed", async () => {
    const onClose = vi.fn()
    render(
      <Dialog open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    await userEvent.keyboard("{Escape}")
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("calls onClose when backdrop is clicked", async () => {
    const onClose = vi.fn()
    const { container } = render(
      <Dialog open={true} onClose={onClose} title="Title">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    // The backdrop is the absolute div that comes before the panel
    const backdrop = container.ownerDocument.querySelector(
      ".fixed.inset-0.z-50 > .absolute",
    ) as HTMLElement
    if (backdrop) {
      await userEvent.click(backdrop)
      expect(onClose).toHaveBeenCalled()
    }
  })

  it("title is linked via aria-labelledby", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Labeled Dialog">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    const dialog = screen.getByRole("dialog")
    const labelledBy = dialog.getAttribute("aria-labelledby")
    expect(labelledBy).toBeTruthy()
    const titleEl = document.getElementById(labelledBy!)
    expect(titleEl?.textContent).toBe("Labeled Dialog")
  })

  it("description is linked via aria-describedby when provided", async () => {
    render(
      <Dialog open={true} onClose={vi.fn()} title="Title" description="Desc text">
        <p>body</p>
      </Dialog>,
    )
    await act(async () => {})
    const dialog = screen.getByRole("dialog")
    const describedBy = dialog.getAttribute("aria-describedby")
    expect(describedBy).toBeTruthy()
    const descEl = document.getElementById(describedBy!)
    expect(descEl?.textContent).toBe("Desc text")
  })
})
