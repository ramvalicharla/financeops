import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi } from "vitest"
import { SortableHeader } from "./SortableHeader"

const noSort = { key: "", direction: null } as const

describe("SortableHeader", () => {
  it("renders label text", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="name" currentSort={noSort} onSort={vi.fn()}>
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByText("Name")).toBeInTheDocument()
  })

  it("renders as a th with scope=col", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="name" currentSort={noSort} onSort={vi.fn()}>
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    const th = screen.getByRole("columnheader")
    expect(th).toHaveAttribute("scope", "col")
  })

  it("has aria-sort=none when not the active sort field", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="name" currentSort={noSort} onSort={vi.fn()}>
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "none")
  })

  it("has aria-sort=ascending when sorted asc on this field", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="name"
              currentSort={{ key: "name", direction: "asc" }}
              onSort={vi.fn()}
            >
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending")
  })

  it("has aria-sort=descending when sorted desc on this field", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="name"
              currentSort={{ key: "name", direction: "desc" }}
              onSort={vi.fn()}
            >
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "descending")
  })

  it("has aria-sort=none when a different field is sorted", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="name"
              currentSort={{ key: "amount", direction: "asc" }}
              onSort={vi.fn()}
            >
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "none")
  })

  it("calls onSort with sortKey when button is clicked", async () => {
    const onSort = vi.fn()
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="amount" currentSort={noSort} onSort={onSort}>
              Amount
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    await userEvent.click(screen.getByRole("button"))
    expect(onSort).toHaveBeenCalledWith("amount")
    expect(onSort).toHaveBeenCalledTimes(1)
  })

  it("calls onSort when Enter key is pressed on the button", async () => {
    const onSort = vi.fn()
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="date" currentSort={noSort} onSort={onSort}>
              Date
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    const button = screen.getByRole("button")
    button.focus()
    await userEvent.keyboard("{Enter}")
    expect(onSort).toHaveBeenCalledWith("date")
  })

  it("shows ↕ indicator when not active sort", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader sortKey="name" currentSort={noSort} onSort={vi.fn()}>
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByText("↕")).toBeInTheDocument()
  })

  it("shows ↑ indicator when sorted ascending", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="name"
              currentSort={{ key: "name", direction: "asc" }}
              onSort={vi.fn()}
            >
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByText("↑")).toBeInTheDocument()
  })

  it("shows ↓ indicator when sorted descending", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="name"
              currentSort={{ key: "name", direction: "desc" }}
              onSort={vi.fn()}
            >
              Name
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByText("↓")).toBeInTheDocument()
  })

  it("applies className to th", () => {
    render(
      <table>
        <thead>
          <tr>
            <SortableHeader
              sortKey="x"
              currentSort={noSort}
              onSort={vi.fn()}
              className="custom-class"
            >
              X
            </SortableHeader>
          </tr>
        </thead>
      </table>,
    )
    expect(screen.getByRole("columnheader")).toHaveClass("custom-class")
  })
})
