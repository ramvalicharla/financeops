import { render, screen, act } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { ConfirmDialog } from "./ConfirmDialog"

describe("ConfirmDialog", () => {
  it("does not render when open=false", () => {
    render(
      <ConfirmDialog
        open={false}
        title="Delete"
        description="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("renders title when open=true", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Delete Item"
        description="This cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    expect(screen.getByText("Delete Item")).toBeInTheDocument()
  })

  it("renders description when open=true", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Are you absolutely sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    expect(screen.getByText("Are you absolutely sure?")).toBeInTheDocument()
  })

  it("renders custom confirmLabel", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        confirmLabel="Yes, delete"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    expect(screen.getByText("Yes, delete")).toBeInTheDocument()
  })

  it("renders custom cancelLabel", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        cancelLabel="No, keep"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    expect(screen.getByText("No, keep")).toBeInTheDocument()
  })

  it("calls onConfirm when confirm button is clicked", async () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        confirmLabel="Confirm"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    await userEvent.click(screen.getByText("Confirm"))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it("calls onCancel when cancel button is clicked", async () => {
    const onCancel = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        cancelLabel="Cancel"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )
    await act(async () => {})
    await userEvent.click(screen.getByText("Cancel"))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it("prepends warning emoji to title when variant=destructive", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Delete Account"
        description="Permanent action."
        variant="destructive"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    // The dialog title will include ⚠
    expect(screen.getByText(/⚠.*Delete Account/)).toBeInTheDocument()
  })

  it("confirm button has destructive variant class when variant=destructive", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    const confirmButton = screen.getByText("Delete").closest("button")
    // The destructive variant adds a bg-destructive class (from shadcn button variants)
    expect(confirmButton?.className).toContain("destructive")
  })

  it("buttons are disabled when isLoading=true", async () => {
    render(
      <ConfirmDialog
        open={true}
        title="Title"
        description="Desc"
        confirmLabel="Confirm"
        cancelLabel="Cancel"
        isLoading={true}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    await act(async () => {})
    const buttons = screen.getAllByRole("button", { name: /Confirm|Cancel/ })
    for (const btn of buttons) {
      expect(btn).toBeDisabled()
    }
  })
})
